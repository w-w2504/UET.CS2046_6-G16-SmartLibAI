"""Map C09/C13 to C03 with P02's confirmed approved-seed policy."""

from src.schemas.recommend import RecommendationResponse
from src.services.catalog import CatalogError
from src.services.preference import PreferenceDataError, PreferenceInputError
from src.services.recommendation_reasons import recommendation_item


def build_response(snapshot, payload, request_id, *, seed_field="seed_book_ids"):
    """Reject unapproved seeds: 422 invalid_input, POST seed_book_ids / GET id."""
    for bid in payload.seed_book_ids:
        if bid not in snapshot.books:
            raise CatalogError(404 if seed_field == "id" else 422,
                "resource_not_found" if seed_field == "id" else "invalid_input",
                "Không tìm thấy sách đã chọn", seed_field, "recommend")
        if bid not in snapshot.eligible_ids:
            raise CatalogError(422, "invalid_input", "Sách đã chọn chưa có đủ nguồn metadata và summary được duyệt", seed_field, "recommend")
    works = [snapshot.metadata[bid].work_id for bid in payload.seed_book_ids]
    if len(set(works)) != len(works):
        raise CatalogError(422, "invalid_input", "Không chọn nhiều ấn bản cùng tác phẩm", seed_field, "recommend")
    for i, bid in enumerate(payload.exclude_book_ids):
        if bid not in snapshot.books:
            raise CatalogError(422, "invalid_input", "Sách đã ẩn không tồn tại", f"exclude_book_ids.{i}", "recommend")
    excluded_works = {snapshot.metadata[bid].work_id for bid in payload.exclude_book_ids}
    if excluded_works.intersection(works):
        raise CatalogError(422, "invalid_input", "Tác phẩm vừa được chọn vừa bị ẩn", "exclude_book_ids", "recommend")
    if any(bid not in snapshot.ranker.books for bid in payload.seed_book_ids):
        raise CatalogError(503, "service_unavailable", "Vector sách đã chọn chưa sẵn sàng", module="recommend")
    # A catalog-only edition can still hide every indexed edition of its work.
    representative = {book.work_id: bid for bid, book in snapshot.ranker.books.items()}
    excludes = [representative[work] for work in excluded_works if work in representative]
    try:
        hits = snapshot.ranker.recommend(payload.seed_book_ids, exclude_book_ids=excludes,
                                          k=payload.k, filters=payload.filters)
    except PreferenceInputError as exc:
        field = seed_field if exc.field == "seed_book_ids" else exc.field
        if seed_field == "id" and field and field.startswith("filters."):
            field = field[len("filters."):]
        raise CatalogError(422, exc.code, str(exc), field, "recommend") from exc
    except PreferenceDataError as exc:
        raise CatalogError(503, exc.code, "Vector gợi ý chưa sẵn sàng", module="recommend") from exc
    return RecommendationResponse(status="ok" if hits else "no_candidates",
        message=None if hits else "Không còn sách phù hợp",
        items=[recommendation_item(snapshot, hit, payload.seed_book_ids) for hit in hits],
        snapshot_id=snapshot.snapshot_id, request_id=request_id)
