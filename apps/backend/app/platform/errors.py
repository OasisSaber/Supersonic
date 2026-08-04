class PlatformAccessError(PermissionError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthenticationRequired(PlatformAccessError):
    def __init__(self) -> None:
        super().__init__("authentication_required", "A valid server session is required.", 401)


class RoleForbidden(PlatformAccessError):
    def __init__(self, message: str = "The current role cannot issue this command.") -> None:
        super().__init__("role_forbidden", message, 403)


class AuditUnavailable(RuntimeError):
    pass
