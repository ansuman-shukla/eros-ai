"""Custom exception classes used across the application."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        self.resource = resource
        self.identifier = identifier
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(detail)


class UnauthorizedError(Exception):
    """Raised when authentication or authorization fails."""

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(detail)


class InsufficientCoinsError(Exception):
    """Raised when a user attempts to spend more coins than they have."""

    def __init__(self, required: int = 0, available: int = 0):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient coins: need {required}, have {available}"
        )


class SessionNotActiveError(Exception):
    """Raised when an operation is attempted on a non-active session."""

    def __init__(self, session_id: str = ""):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' is not active")
