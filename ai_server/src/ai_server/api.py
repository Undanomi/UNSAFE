from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from .models import (
    CreateMachineRequest,
    DownloadURLResponse,
    GuidancePlan,
    GuidanceRequest,
    MachineInformation,
    SessionResponse,
    SessionState,
    SessionStatus,
    scenario_is_valid_for_machine,
)
from .repository import SessionRepository
from .services.download_signing import DownloadSigner, InvalidDownloadSignatureError
from .services.events import ServerEvent
from .services.scenarios import ScenarioCoordinator
from .services.workflow import (
    DISTRIBUTION_ARTIFACT_TYPE,
    InvalidSessionStateError,
    MachineWorkflow,
)

router = APIRouter(prefix="/v1")
UserHeader = Annotated[str | None, Header(alias="X-Authenticated-User-ID")]
RangeHeader = Annotated[str | None, Header(alias="Range")]
IfRangeHeader = Annotated[str | None, Header(alias="If-Range")]
_ETAG_VALUE = re.compile(r"^[!#-~]+$")
logger = logging.getLogger(__name__)
_RUNNING_WORKFLOW_STATUSES = {
    SessionStatus.GENERATING_CODE,
    SessionStatus.BUILD_QUEUED,
    SessionStatus.BUILDING,
}


def _services(request: Request) -> tuple[SessionRepository, ScenarioCoordinator, MachineWorkflow]:
    return request.app.state.repository, request.app.state.scenarios, request.app.state.workflow


def _signed_download_url(request: Request, state) -> tuple[str, datetime]:
    signer: DownloadSigner = request.app.state.download_signer
    signed = signer.issue(state.session_id, state.build_id, state.artifact.artifact_id)
    url = request.url_for("download_machine", session_id=state.session_id).include_query_params(
        expires=signed.expires,
        signature=signed.signature,
    )
    return str(url), datetime.fromtimestamp(signed.expires, UTC)


def _urls(request: Request, state) -> tuple[str, str | None]:
    events = str(request.url_for("scenario_events", session_id=state.session_id))
    completed = (
        state.status == SessionStatus.COMPLETED
        and state.artifact is not None
        and state.build_id is not None
    )
    download = _signed_download_url(request, state)[0] if completed else None
    return events, download


def _response(request: Request, state) -> SessionResponse:
    events, download = _urls(request, state)
    return SessionResponse(
        **state.model_dump(),
        scenario_events_url=events,
        download_url=download,
        user_flag=state.scenario.user_flag if state.scenario else None,
        system_flag=state.scenario.system_flag if state.scenario else None,
    )


def _authorize(state, user_id: str | None) -> None:
    if (user_id or "local-user") != state.owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")


async def _cancel_stale_running_state(request: Request, state: SessionState) -> SessionState:
    repository, scenarios, workflow = _services(request)
    stale_scenario, stale_workflow = _stale_running_phases(state, scenarios, workflow)
    if not stale_scenario and not stale_workflow:
        return state

    try:
        if stale_scenario:
            await scenarios.cancel(state.session_id)
        if stale_workflow:
            await workflow.cancel(state.session_id)
    except Exception:
        logger.warning(
            "failed to cancel stale external work",
            exc_info=True,
            extra={"session_id": state.session_id},
        )
    state = await repository.get(state.session_id)
    state.status = SessionStatus.CANCELLED
    if state.build_id and state.build_status not in {"completed", "failed"}:
        state.build_status = "cancelled"
    state.error_message = None
    return await repository.save(state)


def _stale_running_phases(
    state: SessionState,
    scenarios: ScenarioCoordinator,
    workflow: MachineWorkflow,
) -> tuple[bool, bool]:
    return (
        state.status == SessionStatus.GENERATING_SCENARIO
        and not scenarios.is_running(state.session_id),
        state.status in _RUNNING_WORKFLOW_STATUSES and not workflow.is_running(state.session_id),
    )


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: Request, user_id: UserHeader = None) -> SessionResponse:
    repository, _, _ = _services(request)
    state = await repository.create(user_id or "local-user")
    return _response(request, state)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    request: Request,
    response: Response,
    user_id: UserHeader = None,
) -> SessionResponse:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    state = await _cancel_stale_running_state(request, state)
    state = await workflow.refresh_distribution_artifact(state)
    response.headers["Cache-Control"] = "private, no-store"
    return _response(request, state)


@router.put("/sessions/{session_id}/machine-information", response_model=SessionResponse)
async def save_machine_information(
    session_id: str,
    machine_information: MachineInformation,
    request: Request,
    user_id: UserHeader = None,
) -> SessionResponse:
    repository, scenarios, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if any(_stale_running_phases(state, scenarios, workflow)):
        await _cancel_stale_running_state(request, state)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="stopped machine generation was marked as cancelled; update again",
        )
    if (
        scenarios.is_running(session_id)
        or workflow.is_running(session_id)
        or state.status
        in {
            SessionStatus.GENERATING_SCENARIO,
            *_RUNNING_WORKFLOW_STATUSES,
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="machine generation already started"
        )
    if state.build_id and state.status not in {
        SessionStatus.CANCELLED,
        SessionStatus.COMPLETED,
        SessionStatus.FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="machine generation already started"
        )
    await request.app.state.skills.reset(session_id)
    state.machine_information = machine_information
    state.scenario = None
    state.source_path = None
    state.source_checksum = None
    state.scenario_generation_attempts = 0
    state.scenario_generation_attempt_limit = 0
    state.source_generation_attempts = 0
    state.source_generation_attempt_limit = 0
    state.scenario_sync_attempts = 0
    state.scenario_sync_attempt_limit = 0
    state.build_id = None
    state.build_status = None
    state.build_progress = 0
    state.build_repair_attempts = 0
    state.build_repair_attempt_limit = 0
    state.repair_failure_report = None
    state.machine_access = None
    state.artifact = None
    state.status = SessionStatus.READY
    state.error_message = None
    await repository.save(state)
    return _response(request, state)


@router.get("/sessions/{session_id}/skills")
async def skill_selection_report(
    session_id: str, request: Request, user_id: UserHeader = None
) -> dict:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    state = await workflow.refresh_distribution_artifact(state)
    report = await request.app.state.skills.selection_report(session_id)
    if state.scenario is None:
        report["cve_usage"] = None
    else:
        used = {step.cve_id for step in state.scenario.attack_graph.steps if step.cve_id}
        references = {
            reference["id"]
            for item in report["phases"].get("scenario", [])
            if item["name"] == "cve"
            for reference in item["references"]
        }
        report["cve_usage"] = {
            "used": sorted(used),
            "with_skill_reference": sorted(used & references),
            "without_skill_reference": sorted(used - references),
        }
    return report


@router.get("/sessions/{session_id}/scenarios/events", name="scenario_events")
async def scenario_events(
    session_id: str, request: Request, user_id: UserHeader = None
) -> StreamingResponse:
    repository, scenarios, _ = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if not state.machine_information:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="machine information must be registered first",
        )

    async def stream():
        current = await repository.get(session_id)
        current = await _cancel_stale_running_state(request, current)
        if current.status == SessionStatus.CANCELLED:
            yield ServerEvent("scenario.cancelled", {"session_id": session_id}).encode()
            return
        if current.scenario:
            if current.machine_information and scenario_is_valid_for_machine(
                current.machine_information, current.scenario
            ):
                yield ServerEvent(
                    "scenario.completed", {"scenario": current.scenario.model_dump(mode="json")}
                ).encode()
                return
            current.scenario = None
            current.status = SessionStatus.READY
            current.error_message = None
            await repository.save(current)
        queue = scenarios.broker.subscribe(session_id)
        scenarios.ensure_started(session_id)
        async for event in scenarios.broker.events(session_id, queue):
            yield event.encode()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/cancel", response_model=SessionResponse)
async def cancel_session(
    session_id: str,
    request: Request,
    user_id: UserHeader = None,
) -> SessionResponse:
    repository, scenarios, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if state.status == SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="completed machine generation cannot be cancelled",
        )

    await scenarios.cancel(session_id)
    await workflow.cancel(session_id)
    state = await repository.get(session_id)
    state.status = SessionStatus.CANCELLED
    if state.build_id and state.build_status not in {"completed", "failed"}:
        state.build_status = "cancelled"
    state.error_message = None
    state = await repository.save(state)
    return _response(request, state)


@router.post(
    "/sessions/{session_id}/machines",
    response_model=SessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_machine(
    session_id: str,
    body: CreateMachineRequest,
    request: Request,
    user_id: UserHeader = None,
) -> SessionResponse:
    repository, scenarios, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if any(_stale_running_phases(state, scenarios, workflow)):
        await _cancel_stale_running_state(request, state)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="stopped machine generation was marked as cancelled; retry explicitly",
        )
    try:
        state = await workflow.start(session_id, body.scenario_id)
    except InvalidSessionStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _response(request, state)


@router.post(
    "/sessions/{session_id}/guidance",
    response_model=GuidancePlan,
)
async def create_guidance(
    session_id: str,
    body: GuidanceRequest,
    request: Request,
    response: Response,
    user_id: UserHeader = None,
) -> GuidancePlan:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if (
        state.status != SessionStatus.COMPLETED
        or not state.machine_information
        or not state.scenario
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="machine is not ready")
    if not state.source_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="machine source is unavailable"
        )
    generated = workflow.source_archive.load(state.source_path)
    if generated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="machine source is unavailable"
        )
    guidance = await workflow.generator.generate_guidance(
        state.machine_information,
        state.scenario,
        generated,
        body.acquired_flags,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return guidance


@router.post(
    "/sessions/{session_id}/download-url",
    response_model=DownloadURLResponse,
)
async def create_download_url(
    session_id: str,
    request: Request,
    response: Response,
    user_id: UserHeader = None,
) -> DownloadURLResponse:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    state = await workflow.refresh_distribution_artifact(state)
    if state.status != SessionStatus.COMPLETED or not state.artifact or not state.build_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="machine is not ready")
    if state.artifact.artifact_type != DISTRIBUTION_ARTIFACT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="zip artifact migration is not complete",
        )
    download_url, expires_at = _signed_download_url(request, state)
    response.headers["Cache-Control"] = "private, no-store"
    return DownloadURLResponse(download_url=download_url, expires_at=expires_at)


def _artifact_etag(checksum: str) -> str:
    # Checksums generated by build_server are in the safe `sha256:<hex>` form.
    # Reject quote/control characters defensively before reflecting metadata in a header.
    value = (
        checksum
        if _ETAG_VALUE.fullmatch(checksum) and '"' not in checksum
        else hashlib.sha256(checksum.encode()).hexdigest()
    )
    return f'"{value}"'


@router.get("/sessions/{session_id}/download", name="download_machine")
async def download_machine(
    session_id: str,
    request: Request,
    expires: int,
    signature: str,
    range_header: RangeHeader = None,
    if_range: IfRangeHeader = None,
) -> StreamingResponse:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    if state.status != SessionStatus.COMPLETED or not state.artifact or not state.build_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="machine is not ready")

    signer: DownloadSigner = request.app.state.download_signer
    try:
        signer.validate(
            state.session_id,
            state.build_id,
            state.artifact.artifact_id,
            expires,
            signature,
        )
    except InvalidDownloadSignatureError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error

    state = await workflow.refresh_distribution_artifact(state)
    if not state.artifact or state.artifact.artifact_type != DISTRIBUTION_ARTIFACT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="zip artifact migration is not complete",
        )

    etag = _artifact_etag(state.artifact.checksum)
    upstream_range = range_header
    upstream_if_range = if_range
    if range_header and if_range and if_range == etag:
        # build_server does not expose the checksum ETag itself. Once matched here,
        # omit If-Range so its http.ServeContent can honor the Range request.
        upstream_if_range = None
    elif range_header and if_range and if_range.startswith(('"', "W/")):
        # A mismatched entity-tag requires a complete representation.
        upstream_range = None
        upstream_if_range = None

    upstream = await workflow.build_client.open_download(
        state.build_id,
        state.artifact.artifact_id,
        range_header=upstream_range,
        if_range=upstream_if_range,
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{state.artifact.file_name}"',
        "ETag": etag,
        "Cache-Control": "private, no-store",
        "Referrer-Policy": "no-referrer",
    }
    for header in ("content-length", "content-range", "accept-ranges", "last-modified"):
        if value := upstream.headers.get(header):
            headers[header] = value
    return StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/zip"),
        headers=headers,
        background=BackgroundTask(upstream.aclose),
    )


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    repository, _, _ = _services(request)
    await repository.ping()
    return {"status": "ok"}
