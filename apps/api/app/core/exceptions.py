"""
Domain and API Exception Definitions with RFC 7807 Problem Details representation.
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse

class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        error_code: str = "ERROR",
        invalid_params: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.title = title
        self.error_code = error_code
        self.invalid_params = invalid_params or []

    def to_problem_response(self, request: Request) -> JSONResponse:
        content = {
            "type": f"https://errors.flatmate.platform/{self.error_code.lower()}",
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "error_code": self.error_code,
            "instance": request.url.path,
            "request_id": getattr(request.state, "request_id", None),
        }
        if self.invalid_params:
            content["invalid_params"] = self.invalid_params
        return JSONResponse(
            status_code=self.status_code,
            content=content,
            media_type="application/problem+json"
        )

class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found", error_code: str = "NOT_FOUND"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=detail,
            error_code=error_code,
        )

class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Authentication required or credentials invalid", error_code: str = "UNAUTHORIZED"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail=detail,
            error_code=error_code,
        )

class ForbiddenException(AppException):
    def __init__(self, detail: str = "Access to resource is forbidden", error_code: str = "FORBIDDEN"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail=detail,
            error_code=error_code,
        )

class BadRequestException(AppException):
    def __init__(self, detail: str = "Invalid request payload", error_code: str = "BAD_REQUEST", invalid_params: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Bad Request",
            detail=detail,
            error_code=error_code,
            invalid_params=invalid_params,
        )

class ConflictException(AppException):
    def __init__(self, detail: str = "Resource conflict detected", error_code: str = "CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            title="Conflict",
            detail=detail,
            error_code=error_code,
        )

class RateLimitException(AppException):
    def __init__(self, detail: str = "Rate limit exceeded. Please try again later.", error_code: str = "RATE_LIMITED"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            title="Too Many Requests",
            detail=detail,
            error_code=error_code,
        )

class InternalServerException(AppException):
    def __init__(self, detail: str = "Internal server error occurred", error_code: str = "INTERNAL_SERVER_ERROR"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=detail,
            error_code=error_code,
        )


class ServiceUnavailableException(AppException):
    def __init__(self, detail: str = "This service is temporarily unavailable.", error_code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Service Unavailable",
            detail=detail,
            error_code=error_code,
        )


class PaymentRequiredException(AppException):
    """A paid plan unlocks this. `feature` and `plan` tell the client what to offer."""

    def __init__(self, detail: str, feature: str, plan: str, error_code: str = "UPGRADE_REQUIRED"):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            title="Upgrade Required",
            detail=detail,
            error_code=error_code,
        )
        self.feature = feature
        self.plan = plan

    def to_problem_response(self, request: Request) -> JSONResponse:
        response = super().to_problem_response(request)
        import json

        body = json.loads(response.body)
        body.update({"feature": self.feature, "plan": self.plan})
        return JSONResponse(status_code=self.status_code, content=body, media_type="application/problem+json")
