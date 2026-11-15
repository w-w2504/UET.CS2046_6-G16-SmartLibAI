import re

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import TypeAdapter, ValidationError

from src.schemas.common import ErrorResponse, Filters


def errors(*statuses):
    """Khai báo lỗi theo từng operation, kể cả lỗi nghiệp vụ chưa có service."""
    return {status: {"model": ErrorResponse} for status in (*statuses, 413, 422, 500)}


def query_boundary(*fields):
    async def collect(request: Request):
        params = request.query_params
        errors = []

        def add(field):
            errors.append({"type": "invalid_input", "loc": ("query", field)})

        for field in fields:
            values = params.getlist(field)
            if field not in {"authors", "genres"} and len(values) > 1:
                add(field)
            if field in {"offset", "limit", "k"} and any(
                not re.fullmatch(r"[0-9]+", value) for value in values
            ):
                add(field)
            if field == "has_fulltext" and any(value not in {"true", "false"} for value in values):
                add(field)
        for field in params:
            if field not in fields:
                add(field)
        if request.method == "GET" and await request.body():
            errors.append({"type": "invalid_input", "loc": ("body",)})

        if "authors" in fields:
            try:
                filter_adapter.validate_python({
                    "authors": params.getlist("authors"),
                    "genres": params.getlist("genres"),
                })
            except ValidationError as exc:
                errors.extend(
                    {**error, "loc": ("query", *error["loc"])} for error in exc.errors()
                )

        # FastAPI still validates its declared parameters after this dependency.
        request.state.boundary_errors = errors
        request.state.query_fields = fields

    return [Depends(collect)]


def require_valid_boundary(request: Request):
    # If FastAPI found no errors, the endpoint must still reject boundary errors.
    if errors := getattr(request.state, "boundary_errors", ()):
        request.state.boundary_errors = ()
        raise RequestValidationError(errors)


filter_adapter = TypeAdapter(Filters)
