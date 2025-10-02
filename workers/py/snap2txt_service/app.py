import os, fnmatch
from typing import Iterable, List, Tuple
from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="snap2txt-service (minimal)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DEFAULT_EXCLUDES = {
    "node_modules",".next",".git","__pycache__","dist","build",".DS_Store","Thumbs.db","venv",".tox",".pytest_cache",".mypy_cache",".cache","vendor","package-lock.json","public","reports"
}

def normalize_path(p: str) -> str:
    p = (p or "").strip().strip('"').strip("'")
    return os.path.abspath(os.path.expanduser(p))

def should_exclude(basename: str, relpath: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(relpath, pat):
            return True
    return False

def list_dir_sorted(path: str) -> Tuple[List[str], List[str]]:
    try:
        entries = os.listdir(path)
    except PermissionError:
        return [], []
    dirs, files = [], []
    for name in entries:
        full = os.path.join(path, name)
        if os.path.isdir(full): dirs.append(name)
        else: files.append(name)
    dirs.sort(key=str.lower); files.sort(key=str.lower)
    return dirs, files

def build_tree_lines(root_dir: str, rel: str, exclude_patterns: Iterable[str], include_hidden: bool, ascii_mode: bool) -> List[str]:
    elbow, tee, pipe, space = ("+--", "|  ", "|  ", "   ") if ascii_mode else ("└──", "├──", "│  ", "   ")
    lines: List[str] = []
    current_path = os.path.join(root_dir, rel) if rel else root_dir
    dirs, files = list_dir_sorted(current_path)

    def keep(name: str) -> bool:
        if not include_hidden and name.startswith("."): return False
        rel_child = os.path.join(rel, name) if rel else name
        return not should_exclude(name, rel_child.replace("\\","/"), exclude_patterns)

    dirs = [d for d in dirs if keep(d)]
    files = [f for f in files if keep(f)]
    entries = [(True, d) for d in dirs] + [(False, f) for f in files]

    for idx, (is_dir, name) in enumerate(entries):
        is_last = idx == len(entries) - 1
        branch = elbow if is_last else tee
        lines.append(f"{branch} " + (f"[{name}]" if is_dir else name))
        if is_dir:
            child_rel = os.path.join(rel, name) if rel else name
            child_lines = build_tree_lines(root_dir, child_rel, exclude_patterns, include_hidden, ascii_mode)
            child_prefix = (pipe if not is_last else space)
            lines.extend([child_prefix + l for l in child_lines])
    return lines

class ScanRequest(BaseModel):
    rootDir: str = Field(...)
    includeHidden: bool = False
    ascii: bool = False
    exclude: List[str] = []

class ConcatRequest(BaseModel):
    rootDir: str = Field(...)
    maxBytesPerFile: int = 512*1024
    codeFences: bool = True
    includeHidden: bool = False
    exclude: List[str] = []

@app.post("/scan")
def scan(req: ScanRequest):
    root = normalize_path(req.rootDir)
    if not os.path.isdir(root): return {"error":"Not a directory","root":root}
    patterns = sorted(DEFAULT_EXCLUDES) + list(req.exclude or [])
    header = f"[{os.path.basename(root.rstrip(os.sep))}]"
    lines = [header] + build_tree_lines(root, "", patterns, req.includeHidden, req.ascii)
    return {"text": "\\n".join(lines) + "\\n", "meta": {"files": len(lines)}}

def is_probably_binary(path: str, max_bytes_to_check: int = 8192) -> bool:
    try:
        with open(path, "rb") as fb:
            chunk = fb.read(max_bytes_to_check)
        if b"\\x00" in chunk: return True
        chunk.decode("utf-8")
        return False
    except Exception:
        return True

@app.post("/concat")
def concat(req: ConcatRequest):
    root = normalize_path(req.rootDir)
    if not os.path.isdir(root): return {"error":"Not a directory","root":root}
    patterns = sorted(DEFAULT_EXCLUDES) + list(req.exclude or [])
    written = []
    skipped = []
    for dirpath, dirnames, filenames in os.walk(root):
        pruned = []
        for d in list(dirnames):
            rel_dir = os.path.relpath(os.path.join(dirpath, d), root)
            if (not req.includeHidden and d.startswith(".")) or any(fnmatch.fnmatch(d, p) or fnmatch.fnmatch(rel_dir.replace("\\","/"), p) for p in patterns):
                pruned.append(d)
        for d in pruned:
            try: dirnames.remove(d)
            except: pass
        for fn in filenames:
            if not req.includeHidden and fn.startswith("."): continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\","/")
            base = os.path.basename(full)
            if any(fnmatch.fnmatch(base, p) or fnmatch.fnmatch(rel, p) for p in patterns): continue
            if is_probably_binary(full): skipped.append(f"SKIP(binary): {rel}"); continue
            try:
                size = os.path.getsize(full)
            except OSError:
                skipped.append(f"SKIP(stat): {rel}"); continue
            if size > req.maxBytesPerFile:
                skipped.append(f"SKIP(too-large {size} > {req.maxBytesPerFile}): {rel}"); continue
            try:
                with open(full, "r", encoding="utf-8", errors="strict") as f:
                    content = f.read()
            except Exception:
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    skipped.append(f"WARN(replaced): {rel}")
                except Exception:
                    skipped.append(f"SKIP(read): {rel}"); continue
            header = f"\\n\\n=== {rel} ===\\n"
            if req.codeFences:
                ext = os.path.splitext(full)[1].lower().lstrip(".")
                if ext == "md": ext = ""
                block = header + f"```{ext}\\n" + content + "\\n```\\n"
            else:
                block = header + content + "\\n"
            written.append(block)
    out = "=== PROJECT: " + os.path.basename(root) + " ===\\n\\n" + "".join(written)
    if skipped:
        out += "\\n\\n=== SKIPPED / WARNINGS ===\\n" + "\\n".join(skipped) + "\\n"
    return {"text": out, "meta": {"skipped": len(skipped)}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8801)
