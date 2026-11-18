"""Check C13 correctness with an existing C11 E5 bundle and NumPy, not FAISS."""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from src.schemas.common import Filters
from src.services.preference_source import load_preference_source
from src.services.recommendation import RecommendationRanker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="New JSON file; never overwrite")
    args = parser.parse_args()
    paths = [args.bundle / name for name in ("vectors.npy", "mapping.jsonl", "manifest.json")]
    paths += [args.batch / "catalog.jsonl", args.taxonomy]
    before_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    source = load_preference_source(args.bundle, batch_dir=args.batch, taxonomy_path=args.taxonomy)
    ranker = RecommendationRanker.from_source(source)
    vectors = {bid: source.get_vector(bid) for bid in source.books}
    seeds, works = [], set()
    for bid, book in sorted(source.books.items()):
        if book.work_id not in works:
            seeds.append(bid)
            works.add(book.work_id)
        if len(seeds) == 3:
            break
    if len(seeds) < 3:
        raise ValueError("Integration check needs at least three distinct works")

    def reference(selected, excluded, k, filters):
        # Independent C09 formula and one np.dot per book (not the scorer).
        if len(selected) == 1:
            profile = vectors[selected[0]].copy()
        else:
            mean = [math.fsum(float(vectors[bid][i]) for bid in selected) / len(selected) for i in range(384)]
            norm = math.sqrt(math.fsum(x * x for x in mean))
            profile = np.array([x / norm for x in mean], dtype=np.float32)
        # Isolate dot-product error from profile construction. Check the C09
        # result against the independent formula, then use the SAME float32
        # profile for both dot kernels and the high-precision scalar oracle.
        actual_profile = source.build(selected)
        profile_error = float(np.max(np.abs(actual_profile.astype(np.float64) - profile)))
        assert profile_error <= np.finfo(np.float32).eps
        profile = actual_profile
        actual_scores = ranker.scorer.score_all(profile)
        # Standard forward error bound for a float32 dot product of length n:
        # |computed - exact| <= gamma_n * sum(abs(x_i*y_i)),
        # gamma_n = n*u/(1-n*u), u=eps/2. Two kernels differ by <=2*bound.
        # This bound checks arithmetic only; it NEVER defines ranking ties.
        n = profile.size
        unit_roundoff = float(np.finfo(np.float32).eps) / 2
        gamma_n = n * unit_roundoff / (1 - n * unit_roundoff)
        direct_scores, bounds, errors, scalar_errors = {}, {}, [], []
        for bid, vector in vectors.items():
            products = [float(x) * float(y) for x, y in zip(vector, profile)]
            exact = math.fsum(products)
            bound = gamma_n * math.fsum(abs(x) for x in products)
            direct = np.dot(vector, profile)
            actual = actual_scores[bid]
            assert isinstance(direct, np.float32) and isinstance(actual, np.float32)
            assert abs(float(direct) - exact) <= bound
            assert abs(float(actual) - exact) <= bound
            assert abs(float(actual) - float(direct)) <= 2 * bound
            direct_scores[bid], bounds[bid] = direct, 2 * bound
            errors.append(abs(float(actual) - float(direct)))
            scalar_errors.append(abs(float(actual) - exact))
        blocked = {source.books[bid].work_id for bid in [*selected, *excluded]}
        eligible = []
        for bid, book in source.books.items():
            if book.work_id in blocked:
                continue
            if filters.authors and not any(author in book.authors for author in filters.authors):
                continue
            if filters.genres and not any(code in book.genres for code in filters.genres):
                continue
            if filters.has_fulltext is not None and book.has_fulltext != filters.has_fulltext:
                continue
            eligible.append((bid, book.work_id, direct_scores[bid]))
        eligible.sort(key=lambda item: (-float(item[2]), item[0]))
        expected, seen = [], set()
        for item in eligible:
            if item[1] not in seen:
                expected.append(item)
                seen.add(item[1])
        return expected[:k], bounds, {
            "profile_reference_max_absolute_error": profile_error,
            "profile_reference_absolute_tolerance": float(np.finfo(np.float32).eps),
            "dot_product_unit_roundoff": float(unit_roundoff), "dot_product_gamma_n": float(gamma_n),
            "all_books_max_kernel_difference": max(errors),
            "all_books_max_scalar_reference_error": max(scalar_errors),
            "max_allowed_kernel_difference": max(bounds.values()),
            "arithmetic_bound_passed_for_every_book": True,
        }

    cases = []

    def check(name, selected, excluded=(), k=5, filters=None):
        filters = filters or Filters()
        hits = ranker.recommend(selected, exclude_book_ids=excluded, k=k, filters=filters)
        expected, bounds, numeric_checks = reference(selected, excluded, k, filters)
        assert [hit.book_id for hit in hits] == [item[0] for item in expected]
        assert [hit.work_id for hit in hits] == [item[1] for item in expected]
        for hit, item in zip(hits, expected):
            assert abs(float(hit.score) - float(item[2])) <= bounds[hit.book_id]
        assert [hit.rank for hit in hits] == list(range(1, len(hits) + 1))
        error = max((abs(float(hit.score) - float(item[2])) for hit, item in zip(hits, expected)), default=0)
        cases.append({"name": name, "seed_book_ids": selected, "exclude_book_ids": list(excluded),
            "k": k, "filters": filters.model_dump(), "hits": [asdict(hit) | {"score": float(hit.score)} for hit in hits],
            "reference_max_absolute_error": error, "top_k_matches_reference": True,
            "numeric_checks": numeric_checks})
        return hits

    one = check("one_seed", seeds[:1])
    check("two_seeds", seeds[:2])
    check("three_seeds", seeds)
    if not one:
        raise ValueError("Integration dataset needs an eligible candidate for the hide check")
    hidden = one[0].book_id
    after_hide = check("hide_first_result", seeds[:1], [hidden, hidden])
    assert source.books[hidden].work_id not in {hit.work_id for hit in after_hide}
    check("k_1", seeds[:1], k=1)
    check("k_10", seeds[:1], k=10)
    target = source.books[hidden]
    check("author_genre_and_metadata_only", seeds[:1], k=10,
          filters=Filters(authors=list(target.authors), genres=list(target.genres), has_fulltext=False))
    check("fulltext_only_empty", seeds[:1], filters=Filters(has_fulltext=True))
    for bid, vector in vectors.items():
        np.testing.assert_array_equal(source.get_vector(bid), vector)
        np.testing.assert_array_equal(ranker.scorer.get_vector(bid), vector)
    assert before_hashes == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    report = {"task": "C13", "status": "passed", "scoring_backend": "numpy_exhaustive_float32",
        "faiss_integration_checked": False, "quality_evaluation_performed": False,
        "python": sys.version.split()[0], "interpreter": sys.executable, "numpy": np.__version__,
        "bundle": str(source.bundle_dir), "dataset_id": ranker.dataset_id,
        "book_count": len(source.books), "manifest": json.loads((args.bundle / "manifest.json").read_bytes()),
        "validated_hashes": before_hashes, "source_unchanged": True, "cases": cases}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as file:
            file.write(output)
    print(output)


if __name__ == "__main__":
    main()
