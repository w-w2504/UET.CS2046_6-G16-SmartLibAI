"""SPEC 12.4: bound Recommendation/Similar including transport and validation."""

import asyncio
import re
from time import monotonic

from src.middleware.contract import error_response

RECOMMENDATION_DEADLINE_SECONDS = 10.0


class RecommendationDeadlineMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        applies = scope["type"] == "http" and (
            scope["method"] == "POST" and scope["path"] == "/api/v1/recommend"
            or scope["method"] == "GET" and re.fullmatch(r"/api/v1/books/[^/]+/similar", scope["path"]))
        if not applies:
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state["recommendation_deadline"] = monotonic() + RECOMMENDATION_DEADLINE_SECONDS
        started = False

        async def tracked(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        timer = asyncio.timeout(RECOMMENDATION_DEADLINE_SECONDS)
        try:
            async with timer:
                await self.app(scope, receive, tracked)
        except TimeoutError:
            if not timer.expired():
                raise
            if not started:
                response = error_response(state["request_id"], 504, "request_timeout",
                    "Gợi ý quá thời gian cho phép", module="recommend")
                await response(scope, receive, send)
