from enum import IntEnum


class ExitCode(IntEnum):
    OK_NOOP = 0
    OK_CLICKED = 2
    SESSION_EXPIRED = 10
    SANITY_FAILED = 20
    LOCK_ACTIVE = 30
    UNEXPECTED_ERROR = 40

    @property
    def is_success(self) -> bool:
        return self.value < 10
