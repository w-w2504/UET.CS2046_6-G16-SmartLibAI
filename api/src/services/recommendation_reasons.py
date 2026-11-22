"""Deterministic SPEC 10.3/10.5 reasons using metadata of one serving snapshot."""

from src.schemas.recommend import EvidenceField, RecommendationItem


def recommendation_item(snapshot, hit, seed_book_ids) -> RecommendationItem:
    candidate = snapshot.metadata[hit.book_id]
    for kind, field, reason_code, prefix in (
        ("topic", "topics", "shared_topic", "Cùng chủ đề"),
        ("genre", "genres", "shared_genre", "Cùng thể loại"),
    ):
        candidate_codes = set(getattr(candidate, field))
        shared = candidate_codes & {code for bid in seed_book_ids for code in getattr(snapshot.metadata[bid], field)}
        if shared:
            code = min(shared)  # ASCII taxonomy code: BINARY order.
            seed = next(bid for bid in seed_book_ids if code in getattr(snapshot.metadata[bid], field))
            text = f"{prefix} {snapshot.labels[kind][code]} với {snapshot.books[seed].title}"
            evidence = [EvidenceField(book_id=hit.book_id, field=field, value=code, seed_book_id=seed)]
            return RecommendationItem(**snapshot.books[hit.book_id].model_dump(), rank=hit.rank,
                reason_codes=[reason_code], reason_text=text, evidence_fields=evidence)
    evidence = [EvidenceField(book_id=bid, field="summary", value=None, seed_book_id=None)
                for bid in [hit.book_id, *seed_book_ids]]
    return RecommendationItem(**snapshot.books[hit.book_id].model_dump(), rank=hit.rank,
        reason_codes=["content_similarity"], reason_text="Nội dung mô tả gần với sách đã chọn", evidence_fields=evidence)
