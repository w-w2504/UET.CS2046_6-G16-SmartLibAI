"""Compare C13 FAISS and NumPy using one P4 handoff; never encode or activate."""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

import faiss
import numpy as np

from src.schemas.common import Filters
from src.services.recommendation import RecommendationRanker
from src.services.recommendation_faiss import load_faiss_recommendation_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--classroom-demo", action="store_true")
    parser.add_argument("--report", type=Path, help="New JSON report; never overwrite")
    args = parser.parse_args()
    paths = [args.index / name for name in ("index_manifest.json", "mapping.jsonl", "books.faiss")]
    paths += [args.bundle / name for name in ("manifest.json", "mapping.jsonl", "vectors.npy")]
    paths += [args.batch / "catalog.jsonl", args.taxonomy]
    def hashes():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before_hashes = hashes()
    source = load_faiss_recommendation_source(args.index, bundle_dir=args.bundle, batch_dir=args.batch,
        taxonomy_path=args.taxonomy, classroom_demo=args.classroom_demo)
    ranker = source.ranker()
    baseline = RecommendationRanker.from_source(source.preference)
    books = source.preference.books
    vectors = {bid: source.preference.get_vector(bid) for bid in books}
    seeds, works = [], set()
    for bid, book in sorted(books.items()):
        if book.work_id not in works:
            seeds.append(bid); works.add(book.work_id)
        if len(seeds) == 3:
            break
    if len(seeds) != 3:
        raise ValueError("Integration check needs three distinct seed works")
    cases = []

    def check(name, selected, excluded=(), k=5, filters=None):
        filters = filters or Filters()
        hits = ranker.recommend(selected, exclude_book_ids=excluded, k=k, filters=filters)
        numpy_hits = baseline.recommend(selected, exclude_book_ids=excluded, k=k, filters=filters)
        profile = source.preference.build(selected)
        faiss_scores, numpy_scores = source.scorer.score_all(profile), baseline.scorer.score_all(profile)
        differences, bounds, scalar_errors = {}, {}, []
        u = float(np.finfo(np.float32).eps) / 2
        gamma_n = len(profile) * u / (1 - len(profile) * u)
        for bid, vector in vectors.items():
            products = [float(x) * float(y) for x, y in zip(vector, profile)]
            exact, bound = math.fsum(products), gamma_n * math.fsum(abs(p) for p in products)
            fs, ns = faiss_scores[bid], numpy_scores[bid]
            assert isinstance(fs, np.float32) and isinstance(ns, np.float32)
            assert abs(float(fs) - exact) <= bound and abs(float(ns) - exact) <= bound
            differences[bid] = abs(float(fs) - float(ns))
            bounds[bid] = 2 * bound
            assert differences[bid] <= bounds[bid]
            scalar_errors.append(abs(float(fs) - exact))
        blocked = {books[bid].work_id for bid in [*selected, *excluded]}
        eligible = []
        for bid, book in books.items():
            if book.work_id in blocked: continue
            if filters.authors and not any(a in book.authors for a in filters.authors): continue
            if filters.genres and not any(g in book.genres for g in filters.genres): continue
            if filters.has_fulltext is not None and book.has_fulltext != filters.has_fulltext: continue
            eligible.append(bid)
        ordered = sorted(eligible, key=lambda bid: (-float(faiss_scores[bid]), bid))
        expected, seen = [], set()
        for bid in ordered:
            if books[bid].work_id not in seen:
                expected.append(bid); seen.add(books[bid].work_id)
        assert [h.book_id for h in hits] == expected[:k]
        assert [h.rank for h in hits] == list(range(1, len(hits) + 1))
        assert all(h.score == faiss_scores[h.book_id] for h in hits)
        # Report actual order differences; never coerce near scores into ties.
        numpy_order = sorted(eligible, key=lambda bid: (-float(numpy_scores[bid]), bid))
        numpy_positions = {bid: i for i, bid in enumerate(numpy_order)}
        inversions = []
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                if numpy_positions[left] > numpy_positions[right]:
                    assert abs(float(faiss_scores[left]) - float(faiss_scores[right])) <= bounds[left] + bounds[right]
                    inversions.append({"faiss_first": left, "faiss_second": right,
                        "faiss_scores": [float(faiss_scores[left]), float(faiss_scores[right])],
                        "numpy_scores": [float(numpy_scores[left]), float(numpy_scores[right])]})
        cases.append({"name": name, "seed_book_ids": selected, "exclude_book_ids": list(excluded),
            "k": k, "filters": filters.model_dump(),
            "faiss_hits": [asdict(h) | {"score": float(h.score)} for h in hits],
            "numpy_book_ids": [h.book_id for h in numpy_hits],
            "top_k_identical": [h.book_id for h in hits] == [h.book_id for h in numpy_hits],
            "max_score_difference": max(differences.values()),
            "faiss_max_scalar_reference_error": max(scalar_errors),
            "float32_gamma_n": gamma_n, "max_allowed_kernel_difference": max(bounds.values()),
            "faiss_order_matches_spec": True, "eligible_pair_order_differences": inversions})
        return hits

    one = check("one_seed", seeds[:1])
    check("two_seeds", seeds[:2])
    check("three_seeds", seeds)
    if len(one) < 2:
        raise ValueError("Integration check needs at least two eligible works")
    check("hide_result_duplicate_exclude", seeds[:1], [one[0].book_id] * 2)
    check("k_1", seeds[:1], k=1)
    check("k_10", seeds[:1], k=10)
    target = books[one[0].book_id]
    check("combined_filters", seeds[:1], filters=Filters(authors=list(target.authors),
          genres=list(target.genres), has_fulltext=False))
    seed_work = books[seeds[0]].work_id
    representative = {book.work_id: bid for bid, book in books.items() if book.work_id != seed_work}
    kept_works = {h.work_id for h in one[:2]}
    excluded = [bid for work, bid in representative.items() if work not in kept_works]
    assert len(check("fewer_than_k", seeds[:1], excluded, k=10)) == 2
    assert not check("all_works_hidden", seeds[:1], list(representative.values()))
    check("fulltext_only", seeds[:1], filters=Filters(has_fulltext=True))
    for bid, vector in vectors.items():
        np.testing.assert_array_equal(source.preference.get_vector(bid), vector)
        np.testing.assert_array_equal(source.scorer.get_vector(bid), vector)
    assert before_hashes == hashes()
    report = {"task": "C13", "status": "passed", "backend": "C14_FAISS_IndexFlatIP_float32",
        "python": sys.version.split()[0], "interpreter": sys.executable, "faiss": faiss.__version__,
        "numpy": np.__version__, "index_dir": str(source.index_dir), "snapshot_id": source.snapshot_id,
        "dataset_id": ranker.dataset_id, "bundle_manifest_sha256": source.preference.bundle_fingerprint,
        "book_count": len(books), "work_count": len({b.work_id for b in books.values()}),
        "index_data_kind": source.data_kind, "classroom_demo": source.classroom_demo,
        "bundle_manifest": json.loads((args.bundle / "manifest.json").read_bytes()),
        "validated_source_hashes": before_hashes, "source_unchanged": True,
        "encoder_run": False, "quality_evaluated": False, "cases": cases}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as file: file.write(output)
    print(output)


if __name__ == "__main__":
    main()
