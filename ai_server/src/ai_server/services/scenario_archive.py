from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import ValidationError

from ..models import AttackGraph, MachineInformation, ScenarioDraft, ScenarioReview
from .rockyou import strip_rockyou_graph, strip_rockyou_selections

SCENARIO_REVIEW_POLICY_VERSION = 5


class ScenarioDraftArchive:
    """Persist generated scenario attempts beside their eventual source tree."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def record(
        self,
        session_id: str,
        attempt: int,
        scenario: ScenarioDraft,
        review: ScenarioReview | None = None,
        machine: MachineInformation | None = None,
    ) -> None:
        scenario = strip_rockyou_selections(scenario)
        version_root = self.root / session_id / scenario.scenario_version_id
        version_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self._migrate_flat_attempts(version_root)
        attempt_root = version_root / "attempts" / f"{attempt:06d}"
        attempt_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        review_payload = (
            review.model_dump(mode="json")
            if review is not None
            else {"approved": None, "summary": "review pending", "findings": []}
        )
        metadata = {
            "session_id": session_id,
            "attempt": attempt,
            "status": (
                "review_pending"
                if review is None
                else "approved"
                if review.approved
                else "rejected"
            ),
            "scenario_id": scenario.scenario_id,
            "scenario_version_id": scenario.scenario_version_id,
            "title": scenario.title,
            "target_os": scenario.target_os,
            "tags": scenario.tags,
            "review_approved": review.approved if review is not None else None,
            "review_policy_version": (
                SCENARIO_REVIEW_POLICY_VERSION if review is not None else None
            ),
            "machine_information_checksum": (
                self.machine_checksum(machine) if machine is not None else None
            ),
        }
        attempt_files = {
            "scenario.md": scenario.definition,
            "scenario_description.txt": scenario.scenario_description,
            "attack_graph.json": json.dumps(
                scenario.attack_graph.model_dump(mode="json"), ensure_ascii=False, indent=2
            ),
            "review.json": json.dumps(review_payload, ensure_ascii=False, indent=2),
            "metadata.json": json.dumps(metadata, ensure_ascii=False, indent=2),
        }
        latest_files = {
            "scenario.md": scenario.definition,
            "scenario_description.txt": scenario.scenario_description,
            "attack_graph.json": json.dumps(
                scenario.attack_graph.model_dump(mode="json"), ensure_ascii=False, indent=2
            ),
            "scenario_review.json": json.dumps(review_payload, ensure_ascii=False, indent=2),
            "scenario_metadata.json": json.dumps(metadata, ensure_ascii=False, indent=2),
        }
        for name, content in attempt_files.items():
            self._write_atomic(attempt_root / name, content.rstrip() + "\n")
        for name, content in latest_files.items():
            self._write_atomic(version_root / name, content.rstrip() + "\n")

    def promote_latest(
        self,
        session_id: str,
        attempt: int,
        scenario: ScenarioDraft,
        review: ScenarioReview,
        machine: MachineInformation,
    ) -> None:
        """Replace root artifacts after a later workflow synchronizes the scenario."""

        scenario = strip_rockyou_selections(scenario)
        version_root = self.root / session_id / scenario.scenario_version_id
        version_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self._migrate_flat_attempts(version_root)
        review_payload = review.model_dump(mode="json")
        metadata = {
            "session_id": session_id,
            "attempt": attempt,
            "status": "approved" if review.approved else "rejected",
            "scenario_id": scenario.scenario_id,
            "scenario_version_id": scenario.scenario_version_id,
            "title": scenario.title,
            "target_os": scenario.target_os,
            "review_approved": review.approved,
            "review_policy_version": SCENARIO_REVIEW_POLICY_VERSION,
            "machine_information_checksum": self.machine_checksum(machine),
            "promoted_after_source_sync": True,
        }
        latest_files = {
            "scenario.md": scenario.definition,
            "scenario_description.txt": scenario.scenario_description,
            "attack_graph.json": json.dumps(
                scenario.attack_graph.model_dump(mode="json"), ensure_ascii=False, indent=2
            ),
            "scenario_review.json": json.dumps(
                review_payload, ensure_ascii=False, indent=2
            ),
            "scenario_metadata.json": json.dumps(
                metadata, ensure_ascii=False, indent=2
            ),
        }
        for name, content in latest_files.items():
            self._write_atomic(version_root / name, content.rstrip() + "\n")

    def start_attempt(
        self,
        session_id: str,
        attempt: int,
        machine: MachineInformation | None = None,
        scenario_version_id: str = "v1",
    ) -> None:
        attempt_root = self._attempt_root(session_id, scenario_version_id, attempt)
        metadata = {
            "session_id": session_id,
            "attempt": attempt,
            "status": "started",
            "scenario_version_id": scenario_version_id,
            "machine_information_checksum": (
                self.machine_checksum(machine) if machine is not None else None
            ),
        }
        self._write_atomic(
            attempt_root / "metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        )

    def record_attack_graph(
        self,
        session_id: str,
        attempt: int,
        graph: AttackGraph,
        scenario_version_id: str = "v1",
    ) -> None:
        graph = strip_rockyou_graph(graph)
        attempt_root = self._attempt_root(session_id, scenario_version_id, attempt)
        metadata = self._read_attempt_metadata(attempt_root)
        metadata["status"] = "attack_graph_ready"
        self._write_atomic(
            attempt_root / "attack_graph.json",
            json.dumps(graph.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        )
        self._write_atomic(
            attempt_root / "metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        )

    def record_failure(
        self,
        session_id: str,
        attempt: int,
        phase: str,
        error: Exception,
        scenario_version_id: str = "v1",
    ) -> None:
        attempt_root = self._attempt_root(session_id, scenario_version_id, attempt)
        message = str(error).strip() or error.__class__.__name__
        failure = {
            "status": "failed",
            "phase": phase,
            "error_type": error.__class__.__name__,
            "message": message,
        }
        metadata = self._read_attempt_metadata(attempt_root)
        metadata.update({"status": "failed", "failure_phase": phase})
        self._write_atomic(
            attempt_root / "failure.json",
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n",
        )
        self._write_atomic(
            attempt_root / "metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        )

    def load_latest(
        self,
        session_id: str,
        machine: MachineInformation,
        scenario_version_id: str = "v1",
    ) -> tuple[ScenarioDraft, ScenarioReview | None] | None:
        version_root = self.root / session_id / scenario_version_id
        try:
            metadata = json.loads((version_root / "scenario_metadata.json").read_text())
            if metadata.get("machine_information_checksum") != self.machine_checksum(machine):
                return None
            scenario = ScenarioDraft(
                scenario_id=metadata["scenario_id"],
                scenario_version_id=metadata["scenario_version_id"],
                title=metadata["title"],
                scenario_description=(
                    version_root / "scenario_description.txt"
                ).read_text().strip(),
                definition=(version_root / "scenario.md").read_text().strip(),
                target_os=metadata["target_os"],
                attack_graph=AttackGraph.model_validate_json(
                    (version_root / "attack_graph.json").read_text()
                ),
                tags=metadata.get("tags", []),
            )
            review_value = json.loads((version_root / "scenario_review.json").read_text())
            review = (
                ScenarioReview.model_validate(review_value)
                if isinstance(review_value, dict)
                and isinstance(review_value.get("approved"), bool)
                and metadata.get("review_policy_version")
                == SCENARIO_REVIEW_POLICY_VERSION
                else None
            )
        except (KeyError, OSError, UnicodeError, json.JSONDecodeError, ValidationError):
            return None
        return scenario, review

    def latest_attempt_number(
        self,
        session_id: str,
        scenario_version_id: str = "v1",
    ) -> int:
        version_root = self.root / session_id / scenario_version_id
        if not version_root.is_dir():
            return 0
        self._migrate_flat_attempts(version_root)
        attempts_root = version_root / "attempts"
        if not attempts_root.is_dir():
            return 0
        return max(
            (
                int(path.name)
                for path in attempts_root.iterdir()
                if path.is_dir() and re.fullmatch(r"\d{6,}", path.name)
            ),
            default=0,
        )

    def _attempt_root(
        self,
        session_id: str,
        scenario_version_id: str,
        attempt: int,
    ) -> Path:
        version_root = self.root / session_id / scenario_version_id
        version_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self._migrate_flat_attempts(version_root)
        attempt_root = version_root / "attempts" / f"{attempt:06d}"
        attempt_root.mkdir(parents=True, exist_ok=True, mode=0o750)
        return attempt_root

    @staticmethod
    def _read_attempt_metadata(attempt_root: Path) -> dict:
        try:
            value = json.loads((attempt_root / "metadata.json").read_text())
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def machine_checksum(machine: MachineInformation) -> str:
        payload = json.dumps(
            machine.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _migrate_flat_attempts(version_root: Path) -> None:
        pattern = re.compile(
            r"^(scenario|scenario_description|attack_graph|scenario_review|scenario_metadata)"
            r"\.attempt-(\d{6})\.(md|txt|json)$"
        )
        target_names = {
            "scenario": "scenario.md",
            "scenario_description": "scenario_description.txt",
            "attack_graph": "attack_graph.json",
            "scenario_review": "review.json",
            "scenario_metadata": "metadata.json",
        }
        for source in version_root.iterdir():
            if not source.is_file():
                continue
            match = pattern.fullmatch(source.name)
            if match is None:
                continue
            attempt_root = version_root / "attempts" / match.group(2)
            attempt_root.mkdir(parents=True, exist_ok=True, mode=0o750)
            destination = attempt_root / target_names[match.group(1)]
            if not destination.exists():
                source.replace(destination)
                destination.chmod(0o640)

    @staticmethod
    def _write_atomic(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.chmod(0o640)
        temporary.replace(path)
