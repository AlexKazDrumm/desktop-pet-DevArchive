import base64
import html
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

FIGMA_API_FILE = "https://api.figma.com/v1/files/{file_key}"
FIGMA_API_IMAGES = "https://api.figma.com/v1/images/{file_key}"
REQUEST_TIMEOUT = 30

app = FastAPI(title="Figma Parser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def figma_headers(token: str) -> Dict[str, str]:
    return {"X-Figma-Token": token.strip()}


def fetch_figma_file(token: str, file_key: str) -> Dict[str, Any]:
    url = FIGMA_API_FILE.format(file_key=file_key.strip())
    response = requests.get(
        url, headers=figma_headers(token), timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def fetch_image_urls(
    token: str,
    file_key: str,
    node_ids: List[str],
    image_format: str = "svg",
    scale: float = 1.0,
) -> Dict[str, str]:
    params = {"ids": ",".join(node_ids), "format": image_format}
    if image_format != "svg":
        params["scale"] = str(scale)
    params["use_absolute_bounds"] = "true"
    response = requests.get(
        FIGMA_API_IMAGES.format(file_key=file_key.strip()),
        headers=figma_headers(token),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("images") or {}


class TreeRequest(BaseModel):
    file_key: str = Field(min_length=1)
    token: Optional[str] = None


class PixelExportRequest(BaseModel):
    file_key: str = Field(min_length=1)
    selected_ids: List[str] = Field(min_length=1)
    token: Optional[str] = None
    format: Literal["svg", "png"] = "svg"
    scale: float = Field(default=1.0, gt=0, le=4)


def simplify_tree(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "children": [
            simplify_tree(child) for child in node.get("children", []) or []
        ],
    }


def build_path_map(root: Dict[str, Any]) -> Dict[str, str]:
    result: Dict[str, str] = {}

    def walk(node: Dict[str, Any], path: str) -> None:
        name = node.get("name", "")
        current_path = f"{path}/{name}" if path else name
        node_id = node.get("id")
        if node_id:
            result[node_id] = current_path
        for child in node.get("children", []) or []:
            walk(child, current_path)

    walk(root, "")
    return result


def get_box(node: Dict[str, Any]):
    box = node.get("absoluteBoundingBox")
    if not box:
        return None
    return {
        "x": float(box.get("x", 0)),
        "y": float(box.get("y", 0)),
        "width": float(box.get("width", 0)),
        "height": float(box.get("height", 0)),
    }


def find_nodes_by_ids(root: Dict[str, Any], node_ids: Set[str]):
    result = []

    def walk(node: Dict[str, Any]) -> None:
        if node.get("id") in node_ids:
            result.append(node)
        for child in node.get("children", []) or []:
            walk(child)

    walk(root)
    return result


def compute_bounds(roots: List[Dict[str, Any]]):
    min_x = min_y = 1e9
    max_x = max_y = -1e9
    found = False

    def descendants(node: Dict[str, Any]):
        yield node
        for child in node.get("children", []) or []:
            yield from descendants(child)

    for root in roots:
        for node in descendants(root):
            box = get_box(node)
            if box:
                min_x = min(min_x, box["x"])
                min_y = min(min_y, box["y"])
                max_x = max(max_x, box["x"] + box["width"])
                max_y = max(max_y, box["y"] + box["height"])
                found = True
    if not found:
        return None
    return min_x, min_y, max_x, max_y


def pixel_html(
    file_key: str,
    token: str,
    nodes: List[Dict[str, Any]],
    image_format: str = "svg",
    scale: float = 1.0,
):
    bounds = compute_bounds(nodes)
    if not bounds:
        return {"html": "", "container": {"width": 0, "height": 0}}

    min_x, min_y, max_x, max_y = bounds
    width = int(round(max_x - min_x))
    height = int(round(max_y - min_y))
    offset_x = -int(round(min_x))
    offset_y = -int(round(min_y))
    node_ids = [node["id"] for node in nodes if node.get("id")]
    url_map = fetch_image_urls(
        token, file_key, node_ids, image_format=image_format, scale=scale
    )
    pieces = []

    for node in nodes:
        node_id = node.get("id")
        box = get_box(node)
        if not node_id or not box:
            continue
        url = url_map.get(node_id)
        if not url:
            continue
        left = int(round(box["x"] + offset_x))
        top = int(round(box["y"] + offset_y))
        node_width = int(round(box["width"]))
        node_height = int(round(box["height"]))

        if image_format == "svg":
            try:
                response = requests.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException:
                continue
            svg = re.sub(
                r"<\?xml.*?\?>", "", response.text, flags=re.DOTALL
            ).strip()
            svg = re.sub(r"<!DOCTYPE.*?>", "", svg, flags=re.DOTALL).strip()
            pieces.append(
                f'<div style="position:absolute;left:{left}px;top:{top}px;'
                f'width:{node_width}px;height:{node_height}px;overflow:hidden">'
                f"{svg}</div>"
            )
        else:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            encoded = base64.b64encode(response.content).decode("ascii")
            pieces.append(
                f'<img src="data:image/png;base64,{encoded}" '
                f'style="position:absolute;left:{left}px;top:{top}px;'
                f'width:{node_width}px;height:{node_height}px;" '
                f'alt="node {html.escape(node_id)}" />'
            )
    return {
        "html": "\n".join(pieces),
        "container": {"width": width, "height": height},
    }


def get_token(request_token: Optional[str]) -> str:
    token = (request_token or os.getenv("FIGMA_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    return token


@app.post("/figma/tree")
def api_tree(request: TreeRequest):
    data = fetch_figma_file(get_token(request.token), request.file_key)
    document = data.get("document")
    if not document:
        raise HTTPException(status_code=502, detail="Figma response has no document")
    return {"tree": simplify_tree(document), "idToPath": build_path_map(document)}


@app.post("/figma/export_pixel")
def api_export_pixel(request: PixelExportRequest):
    token = get_token(request.token)
    data = fetch_figma_file(token, request.file_key)
    document = data.get("document")
    if not document:
        raise HTTPException(status_code=502, detail="Figma response has no document")
    selected = find_nodes_by_ids(document, set(request.selected_ids))
    if not selected:
        raise HTTPException(status_code=400, detail="No selected nodes")
    return pixel_html(
        request.file_key,
        token,
        selected,
        image_format=request.format,
        scale=request.scale,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8802)
