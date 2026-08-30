import fnmatch
import os
from typing import Iterable, List, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Project Snapshot Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_EXCLUDES = {
    "node_modules",
    ".next",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".DS_Store",
    "Thumbs.db",
    "venv",
    ".venv",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".cache",
    "vendor",
    "package-lock.json",
    "public",
    "reports",
}


def normalize_path(path: str) -> str:
    path = (path or "").strip().strip('"').strip("'")
    return os.path.abspath(os.path.expanduser(path))


def should_exclude(basename: str, relpath: str, patterns: Iterable[str]) -> bool:
    return any(
        fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(relpath, pattern)
        for pattern in patterns
    )


def list_dir_sorted(path: str) -> Tuple[List[str], List[str]]:
    try:
        entries = os.listdir(path)
    except OSError:
        return [], []

    directories = []
    files = []
    for name in entries:
        full_path = os.path.join(path, name)
        if os.path.isdir(full_path):
            directories.append(name)
        else:
            files.append(name)
    directories.sort(key=str.lower)
    files.sort(key=str.lower)
    return directories, files


def build_tree_lines(
    root_dir: str,
    relative_path: str,
    exclude_patterns: Iterable[str],
    include_hidden: bool,
    ascii_mode: bool,
) -> List[str]:
    elbow, tee, pipe, space = (
        ("+--", "|--", "|  ", "   ")
        if ascii_mode
        else ("└──", "├──", "│  ", "   ")
    )
    lines: List[str] = []
    current_path = (
        os.path.join(root_dir, relative_path) if relative_path else root_dir
    )
    directories, files = list_dir_sorted(current_path)

    def keep(name: str) -> bool:
        if not include_hidden and name.startswith("."):
            return False
        child_path = (
            os.path.join(relative_path, name) if relative_path else name
        )
        return not should_exclude(
            name, child_path.replace("\\", "/"), exclude_patterns
        )

    directories = [name for name in directories if keep(name)]
    files = [name for name in files if keep(name)]
    entries = [(True, name) for name in directories] + [
        (False, name) for name in files
    ]

    for index, (is_directory, name) in enumerate(entries):
        is_last = index == len(entries) - 1
        branch = elbow if is_last else tee
        lines.append(f"{branch} " + (f"[{name}]" if is_directory else name))
        if is_directory:
            child_path = (
                os.path.join(relative_path, name) if relative_path else name
            )
            child_lines = build_tree_lines(
                root_dir,
                child_path,
                exclude_patterns,
                include_hidden,
                ascii_mode,
            )
            prefix = space if is_last else pipe
            lines.extend(prefix + line for line in child_lines)
    return lines


class ScanRequest(BaseModel):
    rootDir: str = Field(min_length=1)
    includeHidden: bool = False
    ascii: bool = False
    exclude: List[str] = Field(default_factory=list)


class ConcatRequest(BaseModel):
    rootDir: str = Field(min_length=1)
    maxBytesPerFile: int = Field(default=512 * 1024, gt=0, le=10 * 1024 * 1024)
    codeFences: bool = True
    includeHidden: bool = False
    exclude: List[str] = Field(default_factory=list)


@app.post("/scan")
def scan(request: ScanRequest):
    root = normalize_path(request.rootDir)
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="Not a directory")

    patterns = sorted(DEFAULT_EXCLUDES) + request.exclude
    header = f"[{os.path.basename(root.rstrip(os.sep))}]"
    lines = [header] + build_tree_lines(
        root, "", patterns, request.includeHidden, request.ascii
    )
    return {"text": "\n".join(lines) + "\n", "meta": {"entries": len(lines) - 1}}


def is_probably_binary(path: str, max_bytes_to_check: int = 8192) -> bool:
    try:
        with open(path, "rb") as file:
            chunk = file.read(max_bytes_to_check)
        if b"\x00" in chunk:
            return True
        chunk.decode("utf-8")
        return False
    except (OSError, UnicodeDecodeError):
        return True


@app.post("/concat")
def concat(request: ConcatRequest):
    root = normalize_path(request.rootDir)
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="Not a directory")

    patterns = sorted(DEFAULT_EXCLUDES) + request.exclude
    written = []
    skipped = []
    for dirpath, dirnames, filenames in os.walk(root):
        for directory in list(dirnames):
            relative_directory = os.path.relpath(
                os.path.join(dirpath, directory), root
            ).replace("\\", "/")
            if (
                not request.includeHidden and directory.startswith(".")
            ) or should_exclude(directory, relative_directory, patterns):
                dirnames.remove(directory)

        for filename in filenames:
            if not request.includeHidden and filename.startswith("."):
                continue
            full_path = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(full_path, root).replace("\\", "/")
            if should_exclude(filename, relative_path, patterns):
                continue
            if is_probably_binary(full_path):
                skipped.append(f"SKIP(binary): {relative_path}")
                continue
            try:
                size = os.path.getsize(full_path)
            except OSError:
                skipped.append(f"SKIP(stat): {relative_path}")
                continue
            if size > request.maxBytesPerFile:
                skipped.append(
                    f"SKIP(too-large {size} > {request.maxBytesPerFile}): {relative_path}"
                )
                continue
            try:
                with open(full_path, "r", encoding="utf-8", errors="strict") as file:
                    content = file.read()
            except UnicodeDecodeError:
                with open(full_path, "r", encoding="utf-8", errors="replace") as file:
                    content = file.read()
                skipped.append(f"WARN(replaced): {relative_path}")
            except OSError:
                skipped.append(f"SKIP(read): {relative_path}")
                continue

            header = f"\n\n=== {relative_path} ===\n"
            if request.codeFences:
                extension = os.path.splitext(full_path)[1].lower().lstrip(".")
                if extension == "md":
                    extension = ""
                block = header + f"```{extension}\n" + content + "\n```\n"
            else:
                block = header + content + "\n"
            written.append(block)

    output = "=== PROJECT: " + os.path.basename(root) + " ===\n\n" + "".join(written)
    if skipped:
        output += "\n\n=== SKIPPED / WARNINGS ===\n" + "\n".join(skipped) + "\n"
    return {"text": output, "meta": {"skipped": len(skipped)}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8801)
