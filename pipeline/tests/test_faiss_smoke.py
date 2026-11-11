import hashlib
import json

import faiss
import numpy as np
import pytest

from ai_library.faiss_smoke import DIMENSION, main, run_smoke_check


def test_roundtrip_uses_real_faiss_and_honest_evidence(tmp_path):
    report = run_smoke_check(tmp_path)
    restored = faiss.read_index(str(tmp_path / "books.faiss"))
    query = np.zeros((1, DIMENSION), dtype=np.float32)
    query[0, 3] = 1
    scores, rows = restored.search(query, 1)

    assert restored.d == 384 and restored.ntotal == 5
    assert rows.tolist() == [[3]]
    np.testing.assert_allclose(scores, [[1]], atol=1e-6, rtol=0)
    assert report["status"] == "passed" and all(report["checks"].values())
    assert report["data_kind"] == "synthetic_fixture"
    assert report["claim"] == "faiss_roundtrip_only"
    assert report["full_system_acceptance"] is False
    assert report["index_sha256"] == hashlib.sha256((tmp_path / "books.faiss").read_bytes()).hexdigest()
    assert json.loads((tmp_path / "smoke-report.json").read_text(encoding="utf-8")) == report


def test_existing_output_is_not_overwritten(tmp_path, capsys):
    sentinel = tmp_path / "books.faiss"
    sentinel.write_bytes(b"existing artefact")
    assert main(["--output-dir", str(tmp_path)]) == 1
    assert sentinel.read_bytes() == b"existing artefact"
    assert not (tmp_path / "smoke-report.json").exists()
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_wrong_search_is_reported_as_failure(tmp_path, monkeypatch, capsys):
    original = faiss.IndexFlatIP.search

    def broken_search(self, queries, k, **kwargs):
        scores, rows = original(self, queries, k, **kwargs)
        return scores + 0.25, rows

    monkeypatch.setattr(faiss.IndexFlatIP, "search", broken_search)
    assert main(["--output-dir", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    assert not (tmp_path / "smoke-report.json").exists()


def test_successful_cli_prints_machine_readable_report(tmp_path, capsys):
    assert main(["--output-dir", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["nearest_rows"] == [0, 1, 2]


def test_output_argument_is_required():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
