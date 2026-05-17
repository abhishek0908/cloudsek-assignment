class AppError(Exception):

    def __init__(
        self,
        message: str,
        error_code: str = "BAD_REQUEST",
        status_code: int = 400,
    ):

        self.message = message
        self.error_code = error_code
        self.status_code = status_code

        super().__init__(message)



class SSRFBlockedError(AppError):

    def __init__(self):

        super().__init__(
            message="Blocked internal/private IP",
            error_code="SSRF_BLOCKED",
            status_code=403,
        )