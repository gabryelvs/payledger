from typing import Any

from fastapi.responses import JSONResponse


def error_response(
    status: int, code: str, message: str, details: Any | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)
