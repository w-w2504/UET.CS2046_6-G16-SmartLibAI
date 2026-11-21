import math
import unittest

from ai_library.bm25_search import BM25Book, BM25Index, build_book_text, tokenize


def make_book(book_id, text, *, authors=(), genres=(), topics=(), fulltext=False, work_id=None):
    return BM25Book(
        book_id=book_id,
        work_id=work_id or f"W_{book_id}",
        title=book_id,
        authors=tuple(authors),
        genres=tuple(genres),
        topics=tuple(topics),
        summary=text,
        has_fulltext=fulltext,
        source_rights_status="approved",
        summary_source_url="https://example.test/book",
        text=text,
    )


class TokenizerTests(unittest.TestCase):
    def test_nfc_casefold_unicode_alphanumeric_and_diacritics(self):
        tokens = tokenize("Học sâu_AI, mô hình-2026! CỐC")
        self.assertEqual(tokens, ("học", "sâu", "ai", "mô", "hình", "2026", "cốc"))

    def test_no_stopwords_are_removed(self):
        self.assertEqual(tokenize("và của những"), ("và", "của", "những"))


class BookRepresentationTests(unittest.TestCase):
    def test_five_lines_follow_spec_and_preserve_empty_topic_line(self):
        raw = {
            "title": "  Học   sâu  ",
            "authors": ["Nguyễn   An", "Bình"],
            "genres": ["lich_su", "khoa_hoc_ky_thuat"],
            "topics": [],
            "summary": "Mô tả   tiếng Việt",
        }
        genres = {"lich_su": "Lịch sử", "khoa_hoc_ky_thuat": "Khoa học kỹ thuật"}
        self.assertEqual(
            build_book_text(raw, genres, {}),
            "Học sâu\nNguyễn An; Bình\nKhoa học kỹ thuật; Lịch sử\n\nMô tả tiếng Việt",
        )


class BM25FormulaTests(unittest.TestCase):
    def test_idf_matches_spec_formula(self):
        index = BM25Index([make_book("B1", "alpha"), make_book("B2", "beta")])
        self.assertAlmostEqual(index.idf("alpha"), math.log(1 + (2 - 1 + 0.5) / (1 + 0.5)))

    def test_term_frequency_and_length_normalization_match_bm25(self):
        index = BM25Index([make_book("B1", "a a b"), make_book("B2", "b")])
        expected = math.log(2) * (2 * (1.5 + 1)) / (2 + 1.5 * (1 - 0.75 + 0.75 * 3 / 2))
        self.assertAlmostEqual(index.score("a", "B1"), expected)


class FilteringAndOrderingTests(unittest.TestCase):
    def test_filters_apply_before_top_k_and_authors_are_or_values(self):
        books = [
            make_book("B_wrong_high", "alpha alpha alpha", authors=("A",), genres=("fiction",)),
            make_book("B_match", "alpha", authors=("B",), genres=("history",), fulltext=True),
            make_book("B_wrong_genre", "alpha alpha", authors=("A",), genres=("fiction",), fulltext=True),
            make_book("B_wrong_author", "alpha alpha", authors=("C",), genres=("history",), fulltext=True),
        ]
        index = BM25Index(books, genre_codes={"fiction", "history"})
        hits = index.search(
            "alpha", k=1,
            filters={"authors": ["A", "B"], "genres": ["history"], "has_fulltext": True},
        )
        self.assertEqual([hit.book_id for hit in hits], ["B_match"])
        self.assertEqual(index.eligible_count({"authors": ["A", "B"], "genres": ["history"], "has_fulltext": True}), 1)

    def test_genres_are_or_values(self):
        index = BM25Index([
            make_book("B_history", "alpha", authors=("B",), genres=("history",)),
            make_book("B_fiction", "alpha", authors=("B",), genres=("fiction",)),
        ], genre_codes={"history", "fiction"})
        hits = index.search("alpha", k=2, filters={"authors": ["B"], "genres": ["history", "fiction"]})
        self.assertEqual([hit.book_id for hit in hits], ["B_fiction", "B_history"])

    def test_ties_use_book_id_and_zero_score_candidates_remain_ranked(self):
        index = BM25Index([make_book("B_z", "unrelated"), make_book("B_a", "unrelated")])
        hits = index.search("absent", k=2)
        self.assertEqual([(hit.book_id, hit.score) for hit in hits], [("B_a", 0.0), ("B_z", 0.0)])

    def test_empty_candidate_set_and_unknown_genre(self):
        index = BM25Index([make_book("B1", "alpha", authors=("A",), genres=("fiction",))], genre_codes={"fiction"})
        self.assertEqual(index.search("alpha", filters={"authors": ["Nobody"]}), [])
        with self.assertRaises(ValueError):
            index.search("alpha", filters={"genres": ["unknown"]})

    def test_editions_are_not_collapsed_by_work_id(self):
        index = BM25Index([
            make_book("B_a", "shared term", work_id="W_same"),
            make_book("B_b", "shared term", work_id="W_same"),
        ])
        self.assertEqual([hit.book_id for hit in index.search("shared", k=2)], ["B_a", "B_b"])

    def test_invalid_k_and_filter_types_are_rejected(self):
        index = BM25Index([make_book("B1", "alpha")])
        for invalid_k in (0, 21, True, 1.0):
            with self.subTest(k=invalid_k), self.assertRaises(ValueError):
                index.search("alpha", k=invalid_k)
        with self.assertRaises(ValueError):
            index.search("alpha", filters={"authors": "A"})


if __name__ == "__main__":
    unittest.main()
