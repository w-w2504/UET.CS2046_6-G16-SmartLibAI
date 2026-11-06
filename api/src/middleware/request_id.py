import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware sinh UUID v4 cho mỗi request và gắn header X-Request-ID theo Mục 12.3."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Luôn sinh UUID v4 mới từ phía server
        req_id = str(uuid.uuid4())
        request.state.request_id = req_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

