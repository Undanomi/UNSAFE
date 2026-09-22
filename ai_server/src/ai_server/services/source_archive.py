from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from ..models import GeneratedSource, ScenarioDraft, SourceFile
from .source_validation import validate_source


class InvalidSourceError(ValueError):
    def __init__(self, message: str, report: dict | None = None) -> None:
        super().__init__(message)
        self.report = report or {"status": "fail", "checks": []}


class SourceArchive:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create(
        self,
        session_id: str,
        scenario: ScenarioDraft,
        generated: GeneratedSource,
        repair_history: list[dict] | None = None,
        skill_snapshot: dict[str, list[dict]] | None = None,
    ) -> tuple[Path, str]:
        version_root = self.root / session_id / scenario.scenario_version_id
        version_root.mkdir(parents=True, exist_ok=True)
        source_root = version_root / "source"
        candidate_root = version_root / "source.candidate"
        if candidate_root.exists():
            shutil.rmtree(candidate_root)
        candidate_root.mkdir(parents=True, exist_ok=True)
        paths: set[str] = set()
        total_size = 0
        for source_file in generated.files:
            relative = self._validate_path(source_file.path)
            normalized = relative.as_posix()
            if normalized in paths:
                raise InvalidSourceError(f"duplicate generated path: {normalized}")
            paths.add(normalized)
            total_size += len(source_file.content.encode("utf-8"))
            if total_size > 5 * 1024 * 1024:
                raise InvalidSourceError("generated source exceeds 5 MiB")
            destination = candidate_root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source_file.content, encoding="utf-8")
            destination.chmod(int(source_file.mode, 8))
        history = repair_history or []
        validation = validate_source(candidate_root, scenario, history)
        (candidate_root / "validation_report.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if history:
            history[-1]["validation_status_after"] = validation["status"]
            history[-1]["validation_summary_after"] = validation["summary"]
        (candidate_root / "repair_report.json").write_text(
            json.dumps({"attempts": history}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        generation_manifest = {
            "scenario_id": scenario.scenario_id,
            "scenario_version_id": scenario.scenario_version_id,
            "attack_graph_checksum": hashlib.sha256(
                scenario.attack_graph.model_dump_json().encode("utf-8")
            ).hexdigest(),
            "generated_at": datetime.now(UTC).isoformat(),
            "written_files": sorted(paths),
            "validation_status": validation["status"],
            "validation_report": "validation_report.json",
            "repair_attempts": len(history),
            "repair_report": "repair_report.json",
            "skills": skill_snapshot or {},
        }
        (candidate_root / "generation_manifest.json").write_text(
            json.dumps(generation_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if validation["status"] != "pass":
            failures = [item["name"] for item in validation["checks"] if item["status"] == "fail"]
            raise InvalidSourceError(
                "generated source validation failed: " + ", ".join(failures), validation
            )
        self._promote_candidate(candidate_root, source_root)
        archive_path = version_root / "source.zip"
        return archive_path, self._write_archive(source_root, archive_path)

    def record_semantic_review(
        self,
        archive_path: Path,
        review_report: dict,
        *,
        approved: bool,
    ) -> str:
        """Persist the final semantic verdict and refresh the submitted archive checksum."""

        source_root = archive_path.parent / "source"
        report_path = source_root / "repair_report.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = {"attempts": []}
        if not isinstance(report, dict):
            report = {"attempts": []}
        report["source_semantic_review"] = {
            "status": "approved" if approved else "rejected",
            "recorded_at": datetime.now(UTC).isoformat(),
            "report": review_report,
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self._write_archive(source_root, archive_path)

    @staticmethod
    def _write_archive(source_root: Path, archive_path: Path) -> str:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(source_root.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo.from_file(path, path.relative_to(source_root).as_posix())
                    info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
                    with path.open("rb") as source:
                        archive.writestr(info, source.read(), compress_type=zipfile.ZIP_DEFLATED)
        os.chmod(archive_path, 0o640)
        return hashlib.sha256(archive_path.read_bytes()).hexdigest()

    @staticmethod
    def _promote_candidate(candidate_root: Path, source_root: Path) -> None:
        previous_root = source_root.with_name("source.previous")
        if previous_root.exists():
            shutil.rmtree(previous_root)
        if source_root.exists():
            source_root.rename(previous_root)
        try:
            candidate_root.rename(source_root)
        except Exception:
            if previous_root.exists() and not source_root.exists():
                previous_root.rename(source_root)
            raise
        if previous_root.exists():
            shutil.rmtree(previous_root)

    def load(self, source_path: str) -> GeneratedSource | None:
        source_root = Path(source_path)
        contents = source_root / "contents"
        if not contents.is_dir():
            return None
        files: list[SourceFile] = []
        for path in sorted(contents.rglob("*")):
            if not path.is_file():
                continue
            mode = "0755" if path.stat().st_mode & 0o111 else "0644"
            files.append(
                SourceFile(
                    path=path.relative_to(source_root).as_posix(),
                    content=path.read_text(encoding="utf-8", errors="replace"),
                    mode=mode,
                )
            )
        return GeneratedSource(files=files) if files else None

    def load_archive(self, archive_path: Path) -> GeneratedSource | None:
        try:
            archive = zipfile.ZipFile(archive_path)
        except (OSError, zipfile.BadZipFile):
            return None
        files: list[SourceFile] = []
        with archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                if info.is_dir() or not info.filename.startswith("contents/"):
                    continue
                try:
                    relative = self._validate_path(info.filename)
                    content = archive.read(info).decode("utf-8")
                except (InvalidSourceError, UnicodeDecodeError, OSError):
                    return None
                mode_bits = (info.external_attr >> 16) & 0o777
                files.append(
                    SourceFile(
                        path=relative.as_posix(),
                        content=content,
                        mode="0755" if mode_bits & 0o111 else "0644",
                    )
                )
        return GeneratedSource(files=files) if files else None

    @staticmethod
    def load_repair_history_from_archive(archive_path: Path) -> list[dict]:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                report = json.loads(archive.read("repair_report.json"))
        except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile):
            return []
        return SourceArchive._repair_attempts(report)

    @staticmethod
    def load_repair_history(source_path: str) -> list[dict]:
        report_path = Path(source_path) / "repair_report.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return SourceArchive._repair_attempts(report)

    @staticmethod
    def _repair_attempts(report: object) -> list[dict]:
        attempts = report.get("attempts") if isinstance(report, dict) else None
        if not isinstance(attempts, list):
            return []
        return [attempt for attempt in attempts if isinstance(attempt, dict)]

    @staticmethod
    def _validate_path(value: str) -> PurePosixPath:
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
            raise InvalidSourceError(f"unsafe generated path: {value}")
        if any(part in {"", "/"} for part in path.parts):
            raise InvalidSourceError(f"invalid generated path: {value}")
        return path
