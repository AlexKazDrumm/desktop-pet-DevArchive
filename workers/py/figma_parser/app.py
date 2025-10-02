import os, re, base64, html
from typing import List, Dict, Any, Optional

import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

FIGMA_API_FILE = "https://api.figma.com/v1/files/{file_key}"
FIGMA_API_NODES = "https://api.figma.com/v1/files/{file_key}/nodes?ids={ids}"
FIGMA_API_IMAGES = "https://api.figma.com/v1/images/{file_key}"

app = FastAPI(title="FigmaParser (sanitized minimal)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def figma_headers(token: str) -> Dict[str,str]:
    return {"X-Figma-Token": token.strip()}

def fetch_figma_file(token: str, file_key: str) -> Dict[str, Any]:
    url = FIGMA_API_FILE.format(file_key=file_key.strip())
    resp = requests.get(url, headers=figma_headers(token))
    resp.raise_for_status()
    return resp.json()

def fetch_images_urls(token: str, file_key: str, ids: List[str], fmt="svg", scale=1.0) -> Dict[str,str]:
    params = {"ids": ",".join(ids), "format": fmt}
    if fmt.lower() != "svg" and scale: params["scale"] = str(scale)
    params["use_absolute_bounds"] = "true"
    resp = requests.get(FIGMA_API_IMAGES.format(file_key=file_key.strip()), headers=figma_headers(token), params=params)
    resp.raise_for_status()
    return resp.json().get("images") or {}

class TreeRequest(BaseModel):
    file_key: str
    token: Optional[str] = None

class PixelExportRequest(BaseModel):
    file_key: str
    selected_ids: List[str]
    token: Optional[str] = None
    format: str = "svg"
    scale: float = 1.0

def simplify_tree(node: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": node.get("id"), "name": node.get("name"), "type": node.get("type"),
            "children": [simplify_tree(ch) for ch in node.get("children",[]) or []]}

def build_path_map(root: Dict[str, Any]) -> Dict[str,str]:
    out: Dict[str,str] = {}
    def walk(n: Dict[str,Any], path: str):
        name = n.get("name","")
        cur = f"{path}/{name}" if path else name
        nid = n.get("id"); 
        if nid: out[nid] = cur
        for ch in n.get("children",[]) or []: walk(ch, cur)
    walk(root,""); return out

def get_box(n: Dict[str,Any]):
    b = n.get("absoluteBoundingBox"); 
    if not b: return None
    return {"x": float(b.get("x",0)), "y": float(b.get("y",0)), "width": float(b.get("width",0)), "height": float(b.get("height",0))}

def find_nodes_by_ids(root: Dict[str,Any], ids: set):
    res=[]; 
    def walk(n):
        if n.get("id") in ids: res.append(n)
        for ch in n.get("children",[]) or []: walk(ch)
    walk(root); return res

def compute_bounds(roots: List[Dict[str,Any]]):
    min_x=min_y=1e9; max_x=max_y=-1e9; found=False
    def iter_sub(n):
        yield n
        for ch in n.get("children",[]) or []: 
            yield from iter_sub(ch)
    for r in roots:
        for n in iter_sub(r):
            b = get_box(n)
            if b:
                min_x=min(min_x,b["x"]); min_y=min(min_y,b["y"])
                max_x=max(max_x,b["x"]+b["width"]); max_y=max(max_y,b["y"]+b["height"]); found=True
    if not found: return None
    return (min_x,min_y,max_x,max_y)

def pixel_html(file_key: str, token: str, nodes: List[Dict[str,Any]], fmt="svg", scale=1.0):
    bounds = compute_bounds(nodes)
    if not bounds: return {"html":"", "container":{"width":0,"height":0}}
    min_x,min_y,max_x,max_y = bounds
    width = int(round(max_x-min_x)); height = int(round(max_y-min_y))
    off_x = -int(round(min_x)); off_y = -int(round(min_y))
    ids = [n.get("id") for n in nodes if n.get("id")]
    url_map = fetch_images_urls(token, file_key, ids, fmt=fmt, scale=scale)
    pieces=[]
    for n in nodes:
        nid = n.get("id"); b = get_box(n)
        if not nid or not b: continue
        url = url_map.get(nid); 
        if not url: continue
        left=int(round(b["x"]+off_x)); top=int(round(b["y"]+off_y))
        w=int(round(b["width"])); h=int(round(b["height"]))
        if fmt.lower()=="svg":
            try:
                r = requests.get(url); r.raise_for_status()
                svg = re.sub(r"<\\?xml.*?\\?>","", r.text, flags=re.DOTALL).strip()
                svg = re.sub(r"<!DOCTYPE.*?>","", svg, flags=re.DOTALL).strip()
                pieces.append(f'<div style="position:absolute;left:{left}px;top:{top}px;width:{w}px;height:{h}px;overflow:hidden">{svg}</div>')
            except: pass
        else:
            r = requests.get(url); r.raise_for_status()
            b64 = base64.b64encode(r.content).decode("ascii")
            pieces.append(f'<img src="data:image/png;base64,{b64}" style="position:absolute;left:{left}px;top:{top}px;width:{w}px;height:{h}px;" alt="node {html.escape(nid)}" />')
    return {"html":"\\n".join(pieces), "container":{"width":width,"height":height}}

@app.post("/figma/tree")
def api_tree(req: TreeRequest):
    token = (req.token or os.getenv("FIGMA_TOKEN") or "").strip()
    if not token: return JSONResponse({"error":"Missing token"}, status_code=400)
    data = fetch_figma_file(token, req.file_key)
    doc = data.get("document")
    if not doc: return JSONResponse({"error":"No document"}, status_code=500)
    return {"tree": simplify_tree(doc), "idToPath": build_path_map(doc)}

@app.post("/figma/export_pixel")
def api_export_pixel(req: PixelExportRequest):
    token = (req.token or os.getenv("FIGMA_TOKEN") or "").strip()
    if not token: return JSONResponse({"error":"Missing token"}, status_code=400)
    fmt = req.format.lower().strip()
    if fmt not in ("svg","png"): return JSONResponse({"error":"format must be svg or png"}, status_code=400)
    data = fetch_figma_file(token, req.file_key)
    doc = data.get("document"); 
    if not doc: return JSONResponse({"error":"No document"}, status_code=500)
    selected = find_nodes_by_ids(doc, set(req.selected_ids))
    if not selected: return JSONResponse({"error":"No selected nodes"}, status_code=400)
    return pixel_html(req.file_key, token, selected, fmt=fmt, scale=float(req.scale or 1.0))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8802)
