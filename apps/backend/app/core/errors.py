from enum import StrEnum


class ErrorCode(StrEnum):
    AI_PROVIDER_ERROR = "ai_provider_error"
    AI_TIMEOUT = "ai_timeout"
    INVALID_MESSAGE = "invalid_message"
    BUSY = "busy"
    INTERNAL_ERROR = "internal_error"


class AppError(Exception):
    """Base error carrying a stable code and a message that is safe to show to the user."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AIProviderError(AppError):
    code = ErrorCode.AI_PROVIDER_ERROR


class AITimeoutError(AIProviderError):
    code = ErrorCode.AI_TIMEOUT


class ConfigError(AppError):
    pass


class InvalidStateTransition(AppError):
    pass


class BusyError(AppError):
    code = ErrorCode.BUSY
