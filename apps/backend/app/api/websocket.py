import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.container import AppContainer
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.protocol import (
    CharacterSummary,
    ClearConversation,
    ClientEvent,
    ErrorEvent,
    SelectCharacter,
    SelectModel,
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
    await connections.send(websocket, await _session_ready(container))

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
            case SelectCharacter(character_id=character_id):
                character = container.characters.get(character_id)
                await container.conversation.switch_character(character)
            case ClearConversation():
                await container.conversation.clear_conversation()
            case SelectModel(model=model):
                await container.conversation.switch_model(model)
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


async def _session_ready(container: AppContainer) -> SessionReady:
    conversation = container.conversation
    character = conversation.character
    return SessionReady(
        character_id=character.id,
        character_name=character.name,
        characters=[CharacterSummary(id=c.id, name=c.name) for c in container.characters.all()],
        history=container.conversation.history(),
        ai_provider=container.provider.name,
        ai_is_remote=container.provider.is_remote,
        ai_model=conversation.model,
        ai_models=await conversation.available_models(),
        ai_model_loading=conversation.model_loading,
        privacy=container.settings.privacy,
        state=container.state.phase,
    )
