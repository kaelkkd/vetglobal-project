from dataclasses import dataclass


@dataclass(slots=True)
class DomainError(Exception):
    status_code: int
    code: str
    message: str


class NotFoundError(DomainError):
    def __init__(self, resource: str) -> None:
        super().__init__(404, f"{resource}_not_found", f"{resource.capitalize()} not found")


class ConflictError(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


class DocumentValidationError(DomainError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code, code, message)
