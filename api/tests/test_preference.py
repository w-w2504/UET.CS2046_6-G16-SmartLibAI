from itertools import permutations

import numpy as np
import pytest

from src.services.preference import (
    InvalidProfileError, PreferenceDataError, PreferenceInputError,
    build_preference_vector,
)


@pytest.fixture
def source():
    vectors = {f"B{i}": np.eye(1, 384, i, dtype=np.float32)[0] for i in range(3)}
    works = {bid: f"W{i}" for i, bid in enumerate(vectors)}
    return vectors, works


def build(ids, source):
    vectors, works = source
    return build_preference_vector(ids, book_to_work=works, get_vector=vectors.__getitem__)


def test_single_seed_copy(source):
    vectors, _ = source
    original = vectors["B1"].copy()
    result = build(["B1"], source)
    np.testing.assert_array_equal(result, original)
    assert result.shape == (384,) and result.dtype == np.float32
    assert not np.shares_memory(result, vectors["B1"])
    result[0] = 99
    np.testing.assert_array_equal(vectors["B1"], original)


@pytest.mark.parametrize("count", [2, 3])
def test_average_order_and_source_preserved(source, count):
    ids = list(source[0])[:count]
    before = {bid: vector.copy() for bid, vector in source[0].items()}
    expected = np.zeros(384, dtype=np.float64)
    expected[:count] = 1 / np.sqrt(count)
    for order in permutations(ids):
        result = build(order, source)
        np.testing.assert_allclose(result, expected, atol=1e-7, rtol=0)
        assert result.shape == (384,) and result.dtype == np.float32
        assert abs(np.linalg.norm(result.astype(np.float64)) - 1) < 1e-5
    for bid in before:
        np.testing.assert_array_equal(source[0][bid], before[bid])


@pytest.mark.parametrize("ids", [[], ["B0"] * 4, "B0", None, [None], [5], [b"B0"], [bytearray(b"B0")], ["bad id"], [""], ["x" * 129], ["missing"], ["B0", "B0"]])
def test_invalid_seeds(source, ids):
    with pytest.raises(PreferenceInputError) as caught:
        build(ids, source)
    assert caught.value.code == "invalid_input" and caught.value.field == "seed_book_ids"


def test_different_editions_same_work_rejected_before_vector_access(source):
    _, works = source
    works["B1"] = works["B0"]
    def forbidden(_):
        pytest.fail("Should validate works before loading vectors")
    with pytest.raises(PreferenceInputError):
        build_preference_vector(["B0", "B1"], book_to_work=works, get_vector=forbidden)


@pytest.mark.parametrize("kind", ["missing", "dimension", "matrix", "zero", "nan", "inf", "not_unit", "float64", "float16", "integer", "list"])
def test_bad_vector_is_data_error(source, kind):
    vectors, _ = source
    vector = vectors["B0"].copy()
    if kind == "missing":
        del vectors["B0"]
    else:
        if kind == "dimension": vector = np.ones(383, dtype=np.float32)
        elif kind == "matrix": vector = vector.reshape(1, 384)
        elif kind == "zero": vector[:] = 0
        elif kind == "nan": vector[2] = np.nan
        elif kind == "inf": vector[2] = np.inf
        elif kind == "not_unit": vector *= 2
        elif kind == "float64": vector = vector.astype(np.float64)
        elif kind == "float16": vector = vector.astype(np.float16)
        elif kind == "integer": vector = vector.astype(np.int32)
        elif kind == "list": vector = vector.tolist()
        vectors["B0"] = vector
    with pytest.raises(PreferenceDataError) as caught:
        build(["B0"], source)
    assert caught.value.code == "service_unavailable"
    assert caught.value.field is None and caught.value.module == "recommend"


@pytest.mark.parametrize("epsilon,valid", [(0, False), (1e-8, False), (2e-8, False), (4e-8, True)])
def test_cancellation_threshold(source, epsilon, valid):
    vectors, _ = source
    vectors["B1"] = -vectors["B0"].copy()
    vectors["B1"][1] = epsilon
    if valid:
        np.testing.assert_array_equal(build(["B0", "B1"], source), np.eye(1, 384, 1, dtype=np.float32)[0])
    else:
        with pytest.raises(InvalidProfileError) as caught:
            build(["B0", "B1"], source)
        assert caught.value.code == "invalid_profile"


def test_exact_threshold_is_inclusive(source, monkeypatch):
    from src.services import preference
    vectors, _ = source
    vectors["B1"] = -vectors["B0"].copy()
    vectors["B1"][1] = np.float32(2e-8)
    boundary = float(np.linalg.norm((vectors["B0"].astype(np.float64) + vectors["B1"]) / 2))
    assert preference.PROFILE_EPSILON == 1e-8
    monkeypatch.setattr(preference, "PROFILE_EPSILON", boundary)
    with pytest.raises(InvalidProfileError):
        build(["B0", "B1"], source)


def test_more_than_twenty_and_exact_edition(source):
    vectors, works = source
    for i in range(3, 401):
        bid = f"B{i}"
        vectors[bid] = vectors["B2"].copy()
        works[bid] = f"W{i}"
    works["B400"] = works["B0"]
    # Same work as B0, but a different edition must keep its own vector.
    np.testing.assert_array_equal(build(["B400"], source), vectors["B400"])
    assert not np.array_equal(build(["B400"], source), vectors["B0"])


@pytest.mark.parametrize("work_id", ["bad work", b"W0", bytearray(b"W0")])
def test_invalid_work_is_source_error(source, work_id):
    source[1]["B0"] = work_id
    with pytest.raises(PreferenceDataError):
        build(["B0"], source)
