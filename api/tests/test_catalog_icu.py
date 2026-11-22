"""C25 real-ICU checks (SPEC 10.4/12.4), using authored catalog data.

Skipped on hosts without PyICU. The ICU acceptance command must explicitly
import icu first so an unavailable runtime cannot be mistaken for a pass.
"""

from contextlib import closing
import sqlite3
import unicodedata

import pytest

pytest.importorskip("icu", reason="C25 real-ICU verification requires PyICU")

from fastapi.testclient import TestClient

from catalog_fixture import BOOK_ID, METADATA_BOOK_ID, create_snapshot, refresh_manifest
from src.config import settings
from src.main import app
from src.services import catalog as service


def test_vietnamese_alphabet_uses_locale_order():
    names = ["Đan", "Ân", "Dân", "Ăn", "An"]
    assert sorted(names, key=service.author_sort_key) == ["An", "Ăn", "Ân", "Dân", "Đan"]


def test_secondary_strength_preserves_accents_but_ignores_case():
    assert service.author_sort_key("ÁNH") == service.author_sort_key("ánh")
    assert service.author_sort_key("An") != service.author_sort_key("Án")


def test_canonical_equivalence_with_normalization_on():
    text = "Nguyễn Ánh"
    assert service.author_sort_key(text) == service.author_sort_key(unicodedata.normalize("NFD", text))


def test_numeric_off_and_punctuation_non_ignorable():
    assert service.author_sort_key("Chương 10") < service.author_sort_key("Chương 2")
    assert service.author_sort_key("AB") != service.author_sort_key("A-B")


def test_real_icu_facets_and_frozen_title_keys(tmp_path, monkeypatch):
    fixture = create_snapshot(tmp_path)
    monkeypatch.setattr(settings, "SNAPSHOT_ROOT", str(fixture["snapshot_root"]))
    monkeypatch.setattr(settings, "CONTROL_ROOT", str(fixture["control_root"]))
    # Deliberately opposite to Unicode byte order: vi_VN orders Ă before Â.
    with closing(sqlite3.connect(fixture["snapshot_dir"] / "catalog.sqlite")) as conn:
        with conn:
            for book_id, name in [(BOOK_ID, "Ăn"), (METADATA_BOOK_ID, "Ân")]:
                conn.execute("UPDATE books SET title=?, title_sort_key=? WHERE book_id=?",
                             (name, service.author_sort_key(name), book_id))
                conn.execute("UPDATE book_authors SET author_name=? WHERE book_id=?", (name, book_id))
    refresh_manifest(fixture["snapshot_dir"])
    with TestClient(app) as client:
        response = client.get("/api/v1/facets")
        assert response.status_code == 200
        assert response.json()["authors"] == ["Ăn", "Ân"]
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()["snapshot_id"] == fixture["snapshot_id"]
        assert response.json()["request_id"] == response.headers["X-Request-ID"]

        def no_runtime_title_keys(_):
            raise AssertionError("Catalog must use frozen SQLite keys, not regenerate them")

        monkeypatch.setattr(service, "author_sort_key", no_runtime_title_keys)
        first = client.get("/api/v1/books?limit=1")
        second = client.get("/api/v1/books?offset=1&limit=1")
        assert first.status_code == second.status_code == 200
        assert first.json()["items"][0]["book_id"] == BOOK_ID
        assert second.json()["items"][0]["book_id"] == METADATA_BOOK_ID
