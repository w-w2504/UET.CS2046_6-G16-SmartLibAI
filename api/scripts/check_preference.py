"""C09 integration against an existing C11 bundle; does not run the encoder."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from src.services.preference_source import load_preference_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="New JSON report file; never overwrite")
    args = parser.parse_args()
    source = load_preference_source(args.bundle, batch_dir=args.batch, taxonomy_path=args.taxonomy)
    # Select three different works, without relying on catalog order or ID names.
    ids, works = [], set()
    for bid, wid in sorted(source.book_to_work.items()):
        if wid not in works:
            ids.append(bid); works.add(wid)
        if len(ids) == 3:
            break
    if len(ids) < 3:
        raise ValueError("Integration check needs at least three different works")
    original_vectors = {bid: source.get_vector(bid) for bid in source.book_to_work}
    matrix_path = args.bundle / "vectors.npy"
    original_file_hash = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    cases = []
    for count in (1, 2, 3):
        seeds = ids[:count]
        result = source.build(seeds)
        assert result.shape == (384,) and result.dtype == np.float32
        norm = float(np.linalg.norm(result.astype(np.float64)))
        assert abs(norm - 1) <= 1e-5
        # Independent summation/normalization, not a call to the C09 core.
        if count == 1:
            expected = original_vectors[seeds[0]].astype(np.float64)
        else:
            average = [math.fsum(float(original_vectors[bid][i]) for bid in seeds) / count for i in range(384)]
            length = math.sqrt(math.fsum(value * value for value in average))
            expected = np.array([value / length for value in average], dtype=np.float64)
        error = float(np.max(np.abs(result.astype(np.float64) - expected)))
        np.testing.assert_allclose(result, expected, atol=1e-7, rtol=0)
        for bid, vector in original_vectors.items():
            np.testing.assert_array_equal(source.get_vector(bid), vector)
        assert hashlib.sha256(matrix_path.read_bytes()).hexdigest() == original_file_hash
        cases.append({"seed_book_ids": seeds, "shape": list(result.shape), "dtype": str(result.dtype),
                      "l2_norm": norm, "independent_max_absolute_error": error, "source_unchanged": True})
    report = {"task": "C09", "data_kind": "existing_c11_bundle", "encoder_run_in_this_check": False,
              "python": sys.version.split()[0], "interpreter": sys.executable, "numpy": np.__version__,
              "bundle": str(source.bundle_dir), "bundle_fingerprint": source.bundle_fingerprint,
              "book_count": len(source.book_to_work), "validated_source_and_artifact_hashes": True,
              "cases": cases, "status": "passed"}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as file:
            file.write(output)
    print(output)


if __name__ == "__main__":
    main()
