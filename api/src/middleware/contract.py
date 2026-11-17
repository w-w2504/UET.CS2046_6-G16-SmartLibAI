from starlette.datastructures import Headers
from starlette.responses import JSONResponse


def error_response(request_id, status, code, message, field=None, module=None, headers=None):
    return JSONResponse(
        {"code": code, "message": message, "field": field, "module": module,
         "request_id": request_id},
        status_code=status,
        headers={**(headers or {}), "X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


class ContractMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 64 * 1024:
                response = error_response(scope["state"]["request_id"], 413, "payload_too_large",
                                          "Nội dung yêu cầu vượt quá 64 KiB")
                await response(scope, receive, send)
                return
            if not message.get("more_body"):
                break
        media_type = Headers(scope=scope).get("content-type", "").partition(";")[0].strip().lower()
        if scope["method"] == "POST" and media_type != "application/json":
            response = error_response(scope["state"]["request_id"], 415, "unsupported_media_type",
                                      "Yêu cầu phải sử dụng định dạng application/json")
            await response(scope, receive, send)
            return

        async def replay():
            nonlocal body
            if body is None:
                return await receive()
            message = {"type": "http.request", "body": bytes(body), "more_body": False}
            body = None
            return message

        await self.app(scope, replay, send)
