"""Request orchestration; pin one snapshot and reuse C09/C13/C14."""

from time import monotonic

from src.services.recommendation_response import build_response, validate_catalog_input
from src.services.recommendation_snapshot import check_deadline, load_recommendation_snapshot


def recommend(payload, request_id, *, seed_field="seed_book_ids", deadline=None):
    deadline = monotonic() + 10 if deadline is None else deadline
    snapshot = load_recommendation_snapshot(payload.snapshot_id, deadline=deadline,
        validate_catalog=lambda catalog: validate_catalog_input(catalog, payload, seed_field=seed_field))
    result = build_response(snapshot, payload, request_id, seed_field=seed_field)
    check_deadline(deadline)
    return result
