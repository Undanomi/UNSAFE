from __future__ import annotations

import json

import pytest

from ai_server.models import (
    AttackGraph,
    AttackStep,
    MachineInformation,
    ScenarioDraft,
    ScenarioReview,
    ScenarioReviewFinding,
    SessionState,
)
from ai_server.services.scenario_archive import ScenarioDraftArchive
from ai_server.services.scenarios import ScenarioAttemptObserver


def scenario(definition: str = "# First draft") -> ScenarioDraft:
    return ScenarioDraft(
        scenario_id="scenario-test",
        title="Test scenario",
        scenario_description="Player-facing description",
        definition=definition,
        tags=["Web", "設定不備"],
        attack_graph=AttackGraph(
            steps=[
                AttackStep(
                    step_id="entry",
                    title="Entry",
                    kind="custom",
                    phase="initial_access",
                    description="Enter the training service.",
                    implementation_steps=["Provision the entry point"],
                )
            ]
        ),
    )


def machine(theme: str = "Web security") -> MachineInformation:
    return MachineInformation(
        name="Test scenario",
        visibility="private",
        theme=theme,
        difficulty="Easy",
    )


def test_records_versioned_scenario_attempts_beside_source_tree(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)
    rejected = ScenarioReview(
        approved=False,
        summary="Needs another pass",
        findings=[
            ScenarioReviewFinding(
                severity="error",
                category="implementation_gap",
                evidence="The implementation plan is incomplete.",
                remediation="Complete the implementation plan.",
            )
        ],
    )
    approved = ScenarioReview(approved=True, summary="Approved", findings=[])

    archive.record("session-1", 3, scenario(), rejected, machine())
    archive.record("session-1", 4, scenario("# Revised draft"), approved, machine())

    version_root = tmp_path / "session-1" / "v1"
    assert (version_root / "attempts/000003/scenario.md").read_text() == "# First draft\n"
    assert (version_root / "attempts/000004/scenario.md").read_text() == "# Revised draft\n"
    assert (version_root / "scenario.md").read_text() == "# Revised draft\n"
    assert (version_root / "scenario_description.txt").read_text() == (
        "Player-facing description\n"
    )
    review = json.loads((version_root / "scenario_review.json").read_text())
    metadata = json.loads((version_root / "scenario_metadata.json").read_text())
    graph = json.loads((version_root / "attack_graph.json").read_text())
    assert review["approved"] is True
    assert metadata["attempt"] == 4
    assert metadata["review_approved"] is True
    assert metadata["tags"] == ["Web", "設定不備"]
    assert graph["steps"][0]["step_id"] == "entry"
    resumed = archive.load_latest("session-1", machine())
    assert resumed is not None
    assert resumed[0].definition == "# Revised draft"
    assert resumed[0].tags == ["Web", "設定不備"]
    assert resumed[1] is not None and resumed[1].approved is True
    assert archive.load_latest("session-1", machine("Changed theme")) is None


def test_promote_latest_updates_root_artifacts_without_rewriting_attempt(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)
    original = scenario()
    original_review = ScenarioReview(approved=True, summary="Initial approval")
    archive.record("session-1", 2, original, original_review, machine())
    synchronized = original.model_copy(
        update={
            "scenario_description": "Synchronized description",
            "definition": "# Synchronized scenario",
        }
    )
    synchronized_review = ScenarioReview(
        approved=True,
        summary="Approved after source synchronization",
    )

    archive.promote_latest(
        "session-1", 2, synchronized, synchronized_review, machine()
    )

    version_root = tmp_path / "session-1" / "v1"
    assert (version_root / "scenario.md").read_text() == "# Synchronized scenario\n"
    assert (version_root / "scenario_description.txt").read_text() == (
        "Synchronized description\n"
    )
    assert json.loads((version_root / "scenario_review.json").read_text())["summary"] == (
        "Approved after source synchronization"
    )
    assert (version_root / "attempts/000002/scenario.md").read_text() == "# First draft\n"
    metadata = json.loads((version_root / "scenario_metadata.json").read_text())
    assert metadata["promoted_after_source_sync"] is True


def test_records_pending_draft_before_review_finishes(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)

    archive.record("session-1", 1, scenario(), machine=machine())

    version_root = tmp_path / "session-1" / "v1"
    review = json.loads((version_root / "attempts/000001/review.json").read_text())
    assert review == {"approved": None, "summary": "review pending", "findings": []}
    resumed = archive.load_latest("session-1", machine())
    assert resumed is not None and resumed[1] is None


def test_ignores_review_saved_under_an_older_review_policy(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)
    approved = ScenarioReview(approved=True, summary="Approved", findings=[])
    archive.record("session-1", 1, scenario(), approved, machine())

    version_root = tmp_path / "session-1" / "v1"
    metadata_path = version_root / "scenario_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.pop("review_policy_version")
    metadata_path.write_text(json.dumps(metadata))

    resumed = archive.load_latest("session-1", machine())

    assert resumed is not None
    assert resumed[0].scenario_id == "scenario-test"
    assert resumed[1] is None


def test_migrates_legacy_flat_attempt_files_on_next_record(tmp_path) -> None:
    version_root = tmp_path / "session-1" / "v1"
    version_root.mkdir(parents=True)
    legacy_files = {
        "scenario.attempt-000001.md": "# Legacy draft\n",
        "scenario_description.attempt-000001.txt": "Legacy description\n",
        "attack_graph.attempt-000001.json": "{}\n",
        "scenario_review.attempt-000001.json": "{}\n",
        "scenario_metadata.attempt-000001.json": "{}\n",
    }
    for name, content in legacy_files.items():
        (version_root / name).write_text(content)

    ScenarioDraftArchive(tmp_path).record("session-1", 2, scenario(), machine=machine())

    migrated = version_root / "attempts" / "000001"
    assert (migrated / "scenario.md").read_text() == "# Legacy draft\n"
    assert (migrated / "scenario_description.txt").read_text() == "Legacy description\n"
    assert (migrated / "attack_graph.json").read_text() == "{}\n"
    assert (migrated / "review.json").read_text() == "{}\n"
    assert (migrated / "metadata.json").read_text() == "{}\n"
    assert not any(version_root.glob("*.attempt-*"))
    assert ScenarioDraftArchive(tmp_path).latest_attempt_number("session-1") == 2


def test_latest_attempt_number_uses_existing_attempt_directories(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)
    archive.record("session-1", 1, scenario(), machine=machine())
    archive.record("session-1", 7, scenario("# Later run"), machine=machine())

    assert archive.latest_attempt_number("session-1") == 7


def test_records_started_partial_and_failed_attempts(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)
    archive.start_attempt("session-1", 1, machine())
    attempt_root = tmp_path / "session-1/v1/attempts/000001"
    assert json.loads((attempt_root / "metadata.json").read_text())["status"] == "started"

    archive.record_attack_graph("session-1", 1, scenario().attack_graph)
    assert (attempt_root / "attack_graph.json").is_file()
    assert json.loads((attempt_root / "metadata.json").read_text())["status"] == (
        "attack_graph_ready"
    )

    archive.record_failure(
        "session-1",
        1,
        "scenario_generation",
        ValueError("invalid scenario JSON"),
    )
    metadata = json.loads((attempt_root / "metadata.json").read_text())
    failure = json.loads((attempt_root / "failure.json").read_text())
    assert metadata["status"] == "failed"
    assert metadata["failure_phase"] == "scenario_generation"
    assert failure == {
        "status": "failed",
        "phase": "scenario_generation",
        "error_type": "ValueError",
        "message": "invalid scenario JSON",
    }


@pytest.mark.asyncio
async def test_attempt_observer_continues_after_archived_attempts(tmp_path) -> None:
    archive = ScenarioDraftArchive(tmp_path)
    archive.record("session-1", 5, scenario(), machine=machine())
    state = SessionState(
        session_id="session-1",
        owner_user_id="user-1",
        machine_information=machine(),
        scenario_generation_attempts=0,
    )

    class Repository:
        async def save(self, saved_state):
            return saved_state

    observer = ScenarioAttemptObserver(Repository(), archive, state)
    await observer()
    await observer.record_draft(scenario("# Retried draft"))

    assert observer.current_attempt == 6
    assert state.scenario_generation_attempts == 1
    assert (tmp_path / "session-1/v1/attempts/000006/scenario.md").read_text() == (
        "# Retried draft\n"
    )
