from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from .models import (
    CreateMachineRequest,
    MachineInformation,
    SessionResponse,
    SessionStatus,
)
from .repository import SessionRepository
from .services.events import ServerEvent
from .services.scenarios import ScenarioCoordinator
from .services.workflow import InvalidSessionStateError, MachineWorkflow

router = APIRouter(prefix="/v1")
UserHeader = Annotated[str | None, Header(alias="X-Authenticated-User-ID")]


def _services(request: Request) -> tuple[SessionRepository, ScenarioCoordinator, MachineWorkflow]:
    return request.app.state.repository, request.app.state.scenarios, request.app.state.workflow


def _urls(request: Request, session_id: str, completed: bool) -> tuple[str, str | None]:
    events = str(request.url_for("scenario_events", session_id=session_id))
    download = (
        str(request.url_for("download_machine", session_id=session_id)) if completed else None
    )
    return events, download


def _response(request: Request, state) -> SessionResponse:
    events, download = _urls(
        request,
        state.session_id,
        state.status == SessionStatus.COMPLETED and state.artifact is not None,
    )
    return SessionResponse(**state.model_dump(), scenario_events_url=events, download_url=download)


def _authorize(state, user_id: str | None) -> None:
    if user_id is not None and user_id != state.owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: Request, user_id: UserHeader = None) -> SessionResponse:
    repository, _, _ = _services(request)
    state = await repository.create(user_id or "local-user")
    return _response(request, state)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str, request: Request, user_id: UserHeader = None
) -> SessionResponse:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    if state.build_id:
        try:
            state = await workflow.synchronize(state)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)
            ) from error
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


@router.get("/sessions/{session_id}/download", name="download_machine")
async def download_machine(
    session_id: str, request: Request, user_id: UserHeader = None
) -> StreamingResponse:
    repository, _, workflow = _services(request)
    state = await repository.get(session_id)
    _authorize(state, user_id)
    state = await workflow.synchronize(state)
    if state.status != SessionStatus.COMPLETED or not state.artifact or not state.build_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="machine is not ready")
    return StreamingResponse(
        workflow.build_client.download(state.build_id, state.artifact.artifact_id),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{state.artifact.file_name}"'},
    )


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, str]:
    repository, _, _ = _services(request)
    await repository.ping()
    return {"status": "ok"}
