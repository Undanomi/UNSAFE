from __future__ import annotations

import pytest

from ai_server.models import GeneratedSource, SourceFile, SourcePatch
from ai_server.services.source_archive import InvalidSourceError
from ai_server.services.source_repair import apply_source_patch


def test_applies_only_changed_files_and_preserves_others() -> None:
    current = GeneratedSource(
        files=[
            SourceFile(path="contents/build.sh", content="old build", mode="0755"),
            SourceFile(path="contents/README.md", content="unchanged"),
        ]
    )
    patch = SourcePatch(
        files=[SourceFile(path="contents/build.sh", content="fixed build", mode="0755")]
    )

    repaired = apply_source_patch(current, patch)

    files = {file.path: file.content for file in repaired.files}
    assert files["contents/build.sh"] == "fixed build"
    assert files["contents/README.md"] == "unchanged"


def test_rejects_patch_outside_contents() -> None:
    current = GeneratedSource(
        files=[SourceFile(path="contents/build.sh", content="old", mode="0755")]
    )
    patch = SourcePatch(files=[SourceFile(path="../escape", content="unsafe")])

    with pytest.raises(InvalidSourceError, match="unsafe repair path"):
        apply_source_patch(current, patch)


def test_rejects_patch_that_rewrites_a_file_with_identical_content() -> None:
    current = GeneratedSource(
        files=[SourceFile(path="contents/README.md", content="unchanged")]
    )
    patch = SourcePatch(
        files=[SourceFile(path="contents/README.md", content="unchanged")]
    )

    with pytest.raises(InvalidSourceError, match="did not make any effective changes"):
        apply_source_patch(current, patch)


def test_rejects_deletion_of_a_missing_file() -> None:
    current = GeneratedSource(
        files=[SourceFile(path="contents/README.md", content="unchanged")]
    )
    patch = SourcePatch(
        files=[SourceFile(path="contents/README.md", content="changed")],
        delete_paths=["contents/missing.txt"],
    )

    with pytest.raises(InvalidSourceError, match="delete path does not exist"):
        apply_source_patch(current, patch)
