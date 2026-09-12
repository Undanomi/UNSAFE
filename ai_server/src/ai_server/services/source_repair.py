from __future__ import annotations

from pathlib import PurePosixPath

from ..models import GeneratedSource, SourcePatch
from .source_archive import InvalidSourceError


def apply_source_patch(current: GeneratedSource, patch: SourcePatch) -> GeneratedSource:
    files = {file.path: file for file in current.files}
    changed_paths: set[str] = set()
    for path in patch.delete_paths:
        normalized = _safe_path(path)
        files.pop(normalized, None)
    for source_file in patch.files:
        normalized = _safe_path(source_file.path)
        files[normalized] = source_file.model_copy(update={"path": normalized})
        changed_paths.add(normalized)
    if not changed_paths and not patch.delete_paths:
        raise InvalidSourceError("repair patch did not contain any changes")
    return GeneratedSource(files=[files[path] for path in sorted(files)])


def _safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or path.parts[0] != "contents"
        or ".." in path.parts
        or "." in path.parts
    ):
        raise InvalidSourceError(f"unsafe repair path: {value}")
    return path.as_posix()
