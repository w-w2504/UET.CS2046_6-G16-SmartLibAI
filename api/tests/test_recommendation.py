"""C13 uses synthetic vectors here; real C11 checks live in check_recommendation.py."""

import numpy as np
import pytest

from src.schemas.common import Filters
from src.services.preference import InvalidProfileError, PreferenceDataError, PreferenceInputError
from src.services.preference_source import BookMetadata
from src.services.recommendation import NumpyBookScorer, RecommendationInputError, RecommendationRanker


def vector(score):
    result = np.zeros(384, dtype=np.float32)
    result[:2] = score, np.sqrt(1 - score * score)
    return result


def make_ranker(books, vectors):
    return RecommendationRanker(books, NumpyBookScorer(tuple(reversed(vectors)), vectors.__getitem__),
        genre_codes=frozenset({"G1", "G2", "unused"}), dataset_id="synthetic_fixture")


@pytest.fixture
def dataset():
    books = {
        "B0": BookMetadata("B0", "W0", ("Seed",), ("G1",), False),
        "B1": BookMetadata("B1", "W1", ("Alice",), ("G1",), False),
        "B2": BookMetadata("B2", "W1", ("Bob",), ("G2",), True),
        "B3": BookMetadata("B3", "W2", ("Bob", "Carol"), ("G2",), True),
        "B4": BookMetadata("B4", "W3", ("Carol",), ("G1", "G2"), False),
        "B5": BookMetadata("B5", "W4", ("Alice",), ("G2",), False),
    }
    vectors = {bid: vector(score) for bid, score in zip(books, [1, .9, .8, .7, .6, .5])}
    return books, vectors


def ids(hits):
    return [hit.book_id for hit in hits]


def test_known_ranking_exact_edition_and_preservation(dataset):
    books, vectors = dataset
    before_books = dict(books)
    before = {bid: value.copy() for bid, value in vectors.items()}
    ranker = make_ranker(books, vectors)
    for _ in range(3):
        hits = ranker.recommend(["B0"])
        assert ids(hits) == ["B1", "B3", "B4", "B5"]
        assert [hit.rank for hit in hits] == [1, 2, 3, 4]
        assert [hit.work_id for hit in hits] == ["W1", "W2", "W3", "W4"]
        for hit in hits:
            assert isinstance(hit.score, np.float32)
            assert hit.score == vectors[hit.book_id][0]
    for bid in vectors:
        np.testing.assert_array_equal(vectors[bid], before[bid])
    assert books == before_books
    with pytest.raises(TypeError):
        ranker.books["new"] = books["B0"]


def test_source_is_snapshotted_and_vector_access_returns_copy(dataset):
    books, vectors = dataset
    ranker = make_ranker(books, vectors)
    vectors["B1"][:] = 0
    books.clear()
    copied = ranker.scorer.get_vector("B1")
    copied[:] = 0
    assert ids(ranker.recommend(["B0"]))[0] == "B1"


def test_seed_and_hidden_work_exclude_all_editions(dataset):
    ranker = make_ranker(*dataset)
    assert not {"B1", "B2"}.intersection(ids(ranker.recommend(["B2"])))
    assert ids(ranker.recommend(["B0"], exclude_book_ids=["B2", "B2"])) == ["B3", "B4", "B5"]
    assert ranker.recommend(["B0"], exclude_book_ids=[]) == ranker.recommend(["B0"])


@pytest.mark.parametrize("filters,expected", [
    ({"authors": [" Bob "]}, ["B2", "B3"]),
    ({"genres": ["G2"]}, ["B2", "B3", "B4", "B5"]),
    ({"has_fulltext": True}, ["B2", "B3"]),
    ({"has_fulltext": False}, ["B1", "B4", "B5"]),
    ({"authors": ["Bob", "Alice"], "genres": ["G1", "G2"], "has_fulltext": True}, ["B2", "B3"]),
    ({"authors": ["Alice"], "genres": ["G2"]}, ["B5"]),
    ({"genres": ["unused"]}, []),
    ({}, ["B1", "B3", "B4", "B5"]),
    (None, ["B1", "B3", "B4", "B5"]),
    ({"authors": [], "genres": [], "has_fulltext": None}, ["B1", "B3", "B4", "B5"]),
    (Filters(authors=["Bob"]), ["B2", "B3"]),
])
def test_filters_before_representative_and_or_and(dataset, filters, expected):
    assert ids(make_ranker(*dataset).recommend(["B0"], filters=filters)) == expected


def test_precise_ties_binary_order_and_no_rounding(dataset):
    books, vectors = dataset
    vectors["B3"] = vectors["B4"] = vector(.5)
    vectors["B5"] = vector(float(np.nextafter(np.float32(.5), np.float32(1))))
    ranker = make_ranker(books, vectors)
    scores = ranker.scorer.score_all(vector(1))
    assert all(isinstance(score, np.float32) for score in scores.values())
    assert scores["B3"] == scores["B4"]
    assert scores["B5"] == np.nextafter(scores["B3"], np.float32(1))
    assert ids(ranker.recommend(["B0"])) == ["B1", "B5", "B3", "B4"]
    vectors["B2"] = vectors["B1"].copy()
    assert ids(make_ranker(books, vectors).recommend(["B0"]))[0] == "B1"


def test_equal_scores_use_ascii_binary_order_for_work_and_edition():
    book_ids = ["seed", "a", "_", "Z", "B2", "B10"]
    books = {bid: BookMetadata(bid, f"W{i}", ("Author",), ("G1",), False)
             for i, bid in enumerate(book_ids)}
    vectors = {bid: vector(1 if bid == "seed" else .5) for bid in book_ids}
    ranker = make_ranker(books, vectors)
    expected = ["B10", "B2", "Z", "_", "a"]
    assert ids(ranker.recommend(["seed"], k=10)) == expected
    # Exact tie between editions chooses B10, which is first under BINARY.
    books["B2"] = BookMetadata("B2", books["B10"].work_id, ("Author",), ("G1",), False)
    assert ids(make_ranker(books, vectors).recommend(["seed"], k=10)) == ["B10", "Z", "_", "a"]


def test_enough_k_after_blocking_many_high_scores_and_more_than_twenty():
    books, vectors = {}, {}
    for i in range(401):
        bid = f"B{i:03}"
        books[bid] = BookMetadata(bid, f"W{i:03}", ("Author",), ("G1",), False)
        vectors[bid] = vector(1 - i / 500)
    ranker = make_ranker(dict(reversed(list(books.items()))), vectors)
    hidden = [f"B{i:03}" for i in range(1, 301)]
    hits = ranker.recommend(["B000"], exclude_book_ids=hidden, k=10)
    assert ids(hits) == [f"B{i:03}" for i in range(301, 311)]
    assert len(ranker.recommend(["B000"], exclude_book_ids=hidden * 2, k=10)) == 10
    with pytest.raises(RecommendationInputError) as error:
        ranker.recommend(["B000"], exclude_book_ids=hidden + ["B301"])
    assert error.value.field == "exclude_book_ids"


def test_no_candidates_and_fewer_than_k(dataset):
    ranker = make_ranker(*dataset)
    assert len(ranker.recommend(["B0"], k=10)) == 4
    assert ranker.recommend(["B0"], exclude_book_ids=["B1", "B3", "B4", "B5"]) == []
    assert len(ranker.recommend(["B0"], k=1)) == 1


@pytest.mark.parametrize("k", [0, 11, -1, True, False, 5.0, 1.5, "5", None])
def test_bad_k(dataset, k):
    with pytest.raises(RecommendationInputError) as error:
        make_ranker(*dataset).recommend(["B0"], k=k)
    assert error.value.field == "k"
    assert error.value.code == "invalid_input" and error.value.module == "recommend"


@pytest.mark.parametrize("hidden", [["missing"], ["bad id"], [bytearray(b"B1")], "B1", None])
def test_invalid_exclude(dataset, hidden):
    with pytest.raises(RecommendationInputError) as error:
        make_ranker(*dataset).recommend(["B0"], exclude_book_ids=hidden)
    assert error.value.field.startswith("exclude_book_ids")
    assert error.value.code == "invalid_input" and error.value.module == "recommend"


def test_seed_hidden_work_conflict(dataset):
    with pytest.raises(RecommendationInputError) as error:
        make_ranker(*dataset).recommend(["B1"], exclude_book_ids=["B2"])
    assert error.value.field == "exclude_book_ids"
    assert error.value.code == "invalid_input" and error.value.module == "recommend"


@pytest.mark.parametrize("seeds", [[], ["missing"], ["B1", "B2"], ["B0", "B0"], ["B0"] * 4])
def test_invalid_seeds_keep_input_meaning(dataset, seeds):
    with pytest.raises(PreferenceInputError) as error:
        make_ranker(*dataset).recommend(seeds)
    assert error.value.code == "invalid_input" and error.value.field.startswith("seed_book_ids")


def test_c09_invalid_profile_propagates(dataset):
    books, vectors = dataset
    vectors["B3"] = -vectors["B0"]
    with pytest.raises(InvalidProfileError) as error:
        make_ranker(books, vectors).recommend(["B0", "B3"])
    assert error.value.code == "invalid_profile"


@pytest.mark.parametrize("filters,field", [
    ({"genres": ["unknown"]}, "filters.genres.0"),
    ({"has_fulltext": "true"}, "filters.has_fulltext"),
    ({"unexpected": 1}, "filters.unexpected"),
    ([], "filters"),
    ("G1", "filters"),
    (True, "filters"),
    ({"authors": "Bob"}, "filters.authors"),
    ({"genres": "G1"}, "filters.genres"),
    ({"genres": [1]}, "filters.genres.0"),
    ({"has_fulltext": 1}, "filters.has_fulltext"),
    ({"authors": None}, "filters.authors"),
])
def test_bad_filters(dataset, filters, field):
    with pytest.raises(RecommendationInputError) as error:
        make_ranker(*dataset).recommend(["B0"], filters=filters)
    assert error.value.field == field
    assert error.value.code == "invalid_input" and error.value.module == "recommend"


@pytest.mark.parametrize("kind", ["missing", "nan", "dtype", "zero", "dimension"])
def test_corrupt_candidate_vector_is_data_error(dataset, kind):
    books, vectors = dataset
    if kind == "missing":
        get_vector = lambda bid: vectors[bid] if bid != "B5" else {}[bid]
    else:
        if kind == "nan": vectors["B5"][0] = np.nan
        elif kind == "zero": vectors["B5"][:] = 0
        elif kind == "dtype": vectors["B5"] = vectors["B5"].astype(np.float64)
        else: vectors["B5"] = np.zeros(383, dtype=np.float32)
        get_vector = vectors.__getitem__
    with pytest.raises(PreferenceDataError):
        NumpyBookScorer(tuple(books), get_vector)


@pytest.mark.parametrize("kind", ["missing", "extra", "nan", "float64", "not_mapping"])
def test_scorer_contract_for_future_c14_adapter(dataset, kind):
    ranker = make_ranker(*dataset)
    scores = dict(ranker.scorer.score_all(vector(1)))
    if kind == "missing": scores.pop("B5")
    elif kind == "extra": scores["unknown"] = np.float32(0)
    elif kind == "nan": scores["B5"] = np.float32(np.nan)
    elif kind == "float64": scores["B5"] = np.float64(.5)
    else: scores = list(scores)
    ranker.scorer.score_all = lambda _: scores
    with pytest.raises(PreferenceDataError):
        ranker.recommend(["B0"])


def test_metadata_vector_ids_must_match(dataset):
    books, vectors = dataset
    books = dict(books)
    books.pop("B5")
    with pytest.raises(PreferenceDataError):
        make_ranker(books, vectors)


def test_multiple_seed_ranking_reference_and_order(dataset):
    from src.services.preference import build_preference_vector
    books, vectors = dataset
    ranker = make_ranker(books, vectors)
    for seeds in (["B0", "B3"], ["B0", "B3", "B4"]):
        profile = build_preference_vector(seeds, book_to_work={b: m.work_id for b, m in books.items()},
                                          get_vector=vectors.__getitem__)
        hits = ranker.recommend(seeds)
        assert hits == ranker.recommend(list(reversed(seeds)))
        for hit in hits:
            np.testing.assert_allclose(hit.score, np.dot(vectors[hit.book_id], profile), atol=1e-7, rtol=0)
