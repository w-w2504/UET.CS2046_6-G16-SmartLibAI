from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from recommendation_fixture import create_snapshot, refresh
from src.config import settings
from src.schemas.recommend import RecommendationRequest
from src.services.catalog import CatalogError
from src.services.recommendation import RecommendationHit
from src.services.recommendation_reasons import recommendation_item
from src.services.recommendation_response import build_response
from src.services.recommendation_snapshot import load_recommendation_snapshot


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    directory = create_snapshot(tmp_path)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(tmp_path / "control"))
    monkeypatch.setattr(settings, "SMARTLIBAI_DEMO_SNAPSHOT", None)
    monkeypatch.setattr(settings, "CLASSROOM_DEMO_SNAPSHOT", None)
    return directory


def response(source, **kwargs):
    return build_response(source, RecommendationRequest(seed_book_ids=["Seed"], **kwargs), str(uuid4()))


def test_serving_faiss_excludes_pending_before_top_k(snapshot):
    source = load_recommendation_snapshot()
    result = response(source)
    assert source.snapshot_id == snapshot.name
    assert len(source.eligible_ids) == 7
    assert [b.book_id for b in result.items] == ["A", "B", "C", "D", "E"]
    assert result.status == "ok" and result.message is None
    assert result.items[0].reason_codes == ["shared_topic"]
    assert result.items[0].evidence_fields[0].seed_book_id == "Seed"
    assert result.items[1].reason_codes == ["content_similarity"]
    assert {f.book_id for f in result.items[1].evidence_fields} == {"Seed", "B"}
    assert result.items[-1].has_fulltext  # serving loader is not metadata-only C11


@pytest.mark.parametrize("defect", ["metadata_only", "summary_only", "missing", "new_pending", "unknown"])
def test_sources_missing_or_unverified_remove_only_the_book(snapshot, defect):
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        if defect == "metadata_only": conn.execute("DELETE FROM sources WHERE book_id='A' AND content_type='summary'")
        elif defect == "summary_only": conn.execute("DELETE FROM sources WHERE book_id='A' AND content_type='metadata'")
        elif defect == "missing": conn.execute("DELETE FROM sources WHERE book_id='A'")
        else:
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute("UPDATE sources SET rights_status=? WHERE book_id='A'", ("pending" if defect == "new_pending" else "unknown",))
        # Make the other edition ineligible too so it cannot represent the work.
        conn.execute("UPDATE sources SET rights_status='pending' WHERE book_id='A_alt'")
        conn.commit()
    refresh(snapshot)
    result = response(load_recommendation_snapshot())
    assert [b.book_id for b in result.items] == ["B", "C", "D", "E"]


def test_additional_pending_source_does_not_cancel_approved_pair(snapshot):
    with closing(sqlite3.connect(snapshot / "catalog.sqlite")) as conn:
        conn.execute("INSERT INTO sources SELECT snapshot_id,'R_extra',book_id,content_type,source_url,source_note,'pending',rights_note,NULL,NULL FROM sources WHERE book_id='A' AND content_type='summary'")
        conn.commit()
    refresh(snapshot)
    assert response(load_recommendation_snapshot()).items[0].book_id == "A"


def test_same_book_different_snapshots_uses_exact_rights(snapshot):
    other = create_snapshot(snapshot.parent.parent, "rec-v2", activate=False)
    with closing(sqlite3.connect(other / "catalog.sqlite")) as conn:
        conn.execute("UPDATE sources SET rights_status='pending' WHERE book_id IN ('A','A_alt')")
        conn.commit()
    refresh(other)
    assert response(load_recommendation_snapshot("rec-v1")).items[0].book_id == "A"
    assert response(load_recommendation_snapshot("rec-v2")).items[0].book_id == "B"
    assert response(load_recommendation_snapshot("rec-v1")).items[0].book_id == "A"


def test_hide_work_filters_and_empty(snapshot):
    source = load_recommendation_snapshot()
    assert [b.book_id for b in response(source, filters={"authors": ["Alternate"]}).items] == ["A_alt"]
    assert [b.book_id for b in response(source, exclude_book_ids=["A_alt", "A_alt"]).items] == ["B", "C", "D", "E"]
    empty = response(source, exclude_book_ids=["A", "B", "C", "D", "E"])
    assert empty.status == "no_candidates" and empty.items == [] and empty.message


def test_manifest_corruption_and_retired_snapshot(snapshot):
    with pytest.raises(CatalogError) as caught:
        load_recommendation_snapshot("retired")
    assert caught.value.status == 404 and caught.value.module == "recommend"
    with (snapshot / "mapping.jsonl").open("ab") as file: file.write(b"corrupt")
    with pytest.raises(CatalogError) as caught:
        load_recommendation_snapshot()
    assert caught.value.status == 503


def test_reason_binary_code_priority_and_seed_order(snapshot):
    source = load_recommendation_snapshot()
    # Immutable metadata replacement is fixture-only; no artifact mutation.
    from dataclasses import replace
    metadata = dict(source.metadata)
    metadata["A"] = replace(metadata["A"], topics=("t2", "t1"))
    metadata["Seed"] = replace(metadata["Seed"], topics=("t2", "t1"))
    metadata["B"] = replace(metadata["B"], topics=("t1",))
    fixture = SimpleNamespace(metadata=metadata, books=source.books, labels=source.labels)
    import numpy as np
    item = recommendation_item(fixture, RecommendationHit("A", "W_A", np.float32(.9), 1), ["B", "Seed"])
    assert item.reason_codes == ["shared_topic"]
    assert item.evidence_fields[0].value == "t1" and item.evidence_fields[0].seed_book_id == "B"
    metadata["A"] = replace(metadata["A"], topics=())
    item = recommendation_item(fixture, RecommendationHit("A", "W_A", np.float32(.9), 1), ["Seed"])
    assert item.reason_codes == ["shared_genre"]
