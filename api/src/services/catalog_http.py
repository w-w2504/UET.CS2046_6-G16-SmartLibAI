"""Strict GET query handling shared by the catalog/reader routes."""

import re
import unicodedata
from contextlib import contextmanager

from fastapi import Request

from src.services.catalog import CatalogError, check_id, invalid
from src.services.snapshot import snapshot_service


def query(request: Request, allowed: set[str], repeated: set[str] | None = None) -> dict:
    repeated = repeated or set()
    params = request.query_params
    for name in params:
        if name not in allowed:
            raise invalid(name, "Tham số không được hỗ trợ")
        if name not in repeated and len(params.getlist(name)) != 1:
            raise invalid(name, "Tham số đơn không được lặp")
    result = dict(params)
    if "snapshot_id" in result:
        check_id(result["snapshot_id"], "snapshot_id")
    for name in repeated:
        values = list(dict.fromkeys(params.getlist(name)))
        if len(values) > 20:
            raise invalid(name, "Mỗi bộ lọc chỉ nhận tối đa 20 giá trị")
        result[name] = values
    return result


def integer(params: dict, name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    value = params.get(name, str(default))
    if not re.fullmatch(r"[0-9]+", value):
        raise invalid(name, "Giá trị phải là số nguyên thập phân")
    try:
        number = int(value)
    except ValueError as exc:
        raise invalid(name) from exc
    if number < minimum or maximum is not None and number > maximum:
        raise invalid(name, "Giá trị nằm ngoài giới hạn cho phép")
    return number


def filters(params: dict) -> tuple[list[str], list[str], bool | None]:
    authors = list(dict.fromkeys(unicodedata.normalize("NFC", value).strip() for value in params["authors"]))
    if any(not value for value in authors):
        raise invalid("authors", "Tên tác giả không được rỗng")
    genres = params["genres"]
    if any(not re.fullmatch(r"[a-z][a-z0-9_]*", value) for value in genres):
        raise invalid("genres", "Thể loại phải dùng mã hợp lệ")
    value = params.get("has_fulltext")
    if value is not None and value not in {"true", "false"}:
        raise invalid("has_fulltext", "Chỉ nhận true hoặc false")
    return authors, genres, None if value is None else value == "true"


@contextmanager
def catalog(snapshot_id: str | None, module: str = "catalog"):
    try:
        with snapshot_service.open_catalog(snapshot_id) as handle:
            yield handle
    except CatalogError as error:
        error.module = module
        raise
