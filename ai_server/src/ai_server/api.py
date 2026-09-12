from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from .models import (
    CreateMachineRequest,
    DownloadURLResponse,
    MachineInformation,
    SessionResponse,
    SessionStatus,
)
from .repository import SessionRepository
from .services.download_signing import DownloadSigner, InvalidDownloadSignatureError
from .services.events import ServerEvent
from .services.scenarios import ScenarioCoordinator
from .services.workflow import InvalidSessionStateError, MachineWorkflow

router = APIRouter(prefix="/v1")
UserHeader = Annotated[str | None, Header(alias="X-Authenticated-User-ID")]
RangeHeader = Annotated[str | None, Header(alias="Range")]
IfRangeHeader = Annotated[str | None, Header(alias="If-Range")]
_ETAG_VALUE = re.compile(r"^[!#-~]+$")


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
    return SessionResponse(**state.model_dump(), scenario_events_url=events, download_url=download)


def _authorize(state, user_id: str | None) -> None:
    if (user_id or "local-user") != state.owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")


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
    if state.build_id:
        try:
            state = await workflow.synchronize(state, auto_repair=False)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)
            ) from error
    response.headers["Cache-Control"] = "private, no-store"
    return _response(request, state)


@router.put("/sessions/{session_id}/machine-information", response_model=SessionResponse)
async def save_machine_information(
    session_id: str,
    machine_information: MachineInformation,
    request: Request,
    user_id: UserHeader = None,
) -> SessionResponse:
    repository, _, _ = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if state.build_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="machine build already started"
        )
    state.machine_information = machine_information
    state.scenario = None
    state.status = SessionStatus.READY
    state.error_message = None
    await repository.save(state)
    return _response(request, state)


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
        if current.scenario:
            yield ServerEvent(
                "scenario.completed", {"scenario": current.scenario.model_dump(mode="json")}
            ).encode()
            return
        queue = scenarios.broker.subscribe(session_id)
        scenarios.ensure_started(session_id)
        async for event in scenarios.broker.events(session_id, queue):
            yield event.encode()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    try:
        state = await workflow.start(session_id, body.scenario_id)
    except InvalidSessionStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _response(request, state)


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
    state = await workflow.synchronize(state, auto_repair=False)
    if state.status != SessionStatus.COMPLETED or not state.artifact or not state.build_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="machine is not ready")
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
        media_type=upstream.headers.get("content-type", "application/zstd"),
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
