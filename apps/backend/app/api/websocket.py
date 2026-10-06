import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.container import AppContainer
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.protocol import (
    ClientEvent,
    ErrorEvent,
    SessionReady,
    SpeechFinished,
    UserMessage,
    client_event_adapter,
)

log = get_logger("ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    container: AppContainer = websocket.app.state.container
    connections = container.connections

    await websocket.accept()
    connections.add(websocket)
    await connections.send(websocket, _session_ready(container))

    pending: set[asyncio.Task[None]] = set()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = client_event_adapter.validate_json(raw)
            except ValidationError:
                log.warning("Rejected invalid client message")
                await connections.send(
                    websocket,
                    ErrorEvent(code=ErrorCode.INVALID_MESSAGE, message="Invalid message format"),
                )
                continue
            # Turns run as tasks so the socket keeps reading (e.g. to answer "busy").
            task = asyncio.create_task(_dispatch(container, websocket, event))
            pending.add(task)
            task.add_done_callback(pending.discard)
    except WebSocketDisconnect:
        pass
    finally:
        connections.remove(websocket)
        for task in pending:
            task.cancel()
        if connections.client_count == 0:
            await container.conversation.finish_speaking()


async def _dispatch(container: AppContainer, websocket: WebSocket, event: ClientEvent) -> None:
    try:
        match event:
            case UserMessage(text=text):
                await container.conversation.handle_user_message(text)
            case SpeechFinished():
                await container.conversation.finish_speaking()
    except AppError as exc:
        await _send_error(container, websocket, ErrorEvent(code=exc.code, message=exc.message))
    except Exception:
        log.exception("Unhandled error while processing client event")
        await _send_error(
            container,
            websocket,
            ErrorEvent(code=ErrorCode.INTERNAL_ERROR, message="Internal server error"),
        )


async def _send_error(container: AppContainer, websocket: WebSocket, error: ErrorEvent) -> None:
    try:
        await container.connections.send(websocket, error)
    except Exception:
        log.debug("Could not deliver error to client")


def _session_ready(container: AppContainer) -> SessionReady:
    return SessionReady(
        character_name=container.character.name,
        ai_provider=container.provider.name,
        ai_is_remote=container.provider.is_remote,
        privacy=container.settings.privacy,
        state=container.state.phase,
    )
