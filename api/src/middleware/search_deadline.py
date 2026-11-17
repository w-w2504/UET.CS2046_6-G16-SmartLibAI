"""SPEC 12.4: bound the entire Search request, including body parsing."""

import asyncio
from time import monotonic

from src.middleware.contract import error_response

SEARCH_DEADLINE_SECONDS = 10.0


class SearchDeadlineMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] != "POST"
                or scope["path"] != "/api/v1/search"):
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state["search_deadline"] = monotonic() + SEARCH_DEADLINE_SECONDS
        started = False

        async def track_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        timer = asyncio.timeout(SEARCH_DEADLINE_SECONDS)
        try:
            async with timer:
                await self.app(scope, receive, track_send)
        except TimeoutError:
            if not timer.expired():
                raise
            if not started:
                response = error_response(state["request_id"], 504, "timeout",
                    "Tìm kiếm quá thời gian cho phép", module="search")
                await response(scope, receive, send)
