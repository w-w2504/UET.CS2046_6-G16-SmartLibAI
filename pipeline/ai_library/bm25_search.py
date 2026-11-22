"""Internal BM25 baseline for Search evaluation; this is not a serving API."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from ai_library.text_utils import normalize_metadata_text

K1 = 1.5
B = 0.75
IDF_FORMULA = "ln(1+(N-df+0.5)/(df+0.5))"
MAX_K = 20
_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class BM25Book:
    book_id: str
    work_id: str
    title: str
    authors: tuple[str, ...]
    genres: tuple[str, ...]
    topics: tuple[str, ...]
    summary: str
    has_fulltext: bool
    source_rights_status: str
    summary_source_url: str
    text: str


@dataclass(frozen=True, slots=True)
class BM25Hit:
    book: BM25Book
    rank: int
    score: float

    @property
    def book_id(self) -> str:
        return self.book.book_id


def tokenize(text: str) -> tuple[str, ...]:
    """NFC + casefold, then split on Unicode letter/digit runs; retain accents."""
    if not isinstance(text, str):
        raise TypeError("Văn bản BM25 phải là chuỗi")
    normalized = unicodedata.normalize("NFC", text).casefold()
    return tuple(_TOKEN_RE.findall(normalized))


def build_book_text(
    book: Mapping[str, object],
    genre_labels: Mapping[str, str],
    topic_labels: Mapping[str, str],
) -> str:
    """Build the same five-line representation used by C11/E5 (SPEC 10.4)."""
    authors = book.get("authors")
    genres = book.get("genres")
    topics = book.get("topics")
    title = book.get("title")
    summary = book.get("summary")
    if not isinstance(title, str) or not isinstance(summary, str):
        raise ValueError("Sách thiếu title hoặc summary")
    if not isinstance(authors, list) or not all(isinstance(x, str) for x in authors):
        raise ValueError("authors phải là danh sách chuỗi")
    if not isinstance(genres, list) or not all(isinstance(x, str) for x in genres):
        raise ValueError("genres phải là danh sách mã")
    if not isinstance(topics, list) or not all(isinstance(x, str) for x in topics):
        raise ValueError("topics phải là danh sách mã")
    try:
        genre_names = [genre_labels[code] for code in sorted(genres)]
        topic_names = [topic_labels[code] for code in sorted(topics)]
    except KeyError as exc:
        raise ValueError(f"Mã taxonomy không có nhãn: {exc.args[0]}") from exc
    lines = (
        title,
        "; ".join(normalize_metadata_text(name) for name in authors),
        "; ".join(normalize_metadata_text(name) for name in genre_names),
        "; ".join(normalize_metadata_text(name) for name in topic_names),
        summary,
    )
    return "\n".join(normalize_metadata_text(line) for line in lines)


def load_catalog(
    catalog_path: Path,
    taxonomy_path: Path,
) -> tuple[list[BM25Book], dict[str, str], dict[str, str]]:
    """Load the selected metadata corpus without requiring model/FAISS packages."""
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    def labels(key: str) -> dict[str, str]:
        values = taxonomy.get(key)
        if not isinstance(values, list):
            raise ValueError(f"Taxonomy {key} phải là danh sách")
        result: dict[str, str] = {}
        for value in values:
            if (not isinstance(value, dict) or not isinstance(value.get("code"), str)
                    or not isinstance(value.get("label"), str) or value["code"] in result):
                raise ValueError(f"Taxonomy {key} sai schema hoặc trùng code")
            result[value["code"]] = value["label"]
        return result

    genre_labels = labels("genres")
    topic_labels = labels("topics")
    books: list[BM25Book] = []
    seen: set[str] = set()
    for line_number, line in enumerate(catalog_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"Dòng catalog rỗng: {line_number}")
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError(f"Dòng catalog không phải object: {line_number}")
        book_id = raw.get("book_id")
        work_id = raw.get("work_id")
        title = raw.get("title")
        summary = raw.get("summary")
        fulltext = raw.get("fulltext_approved")
        if (not isinstance(book_id, str) or not book_id or book_id in seen
                or not isinstance(work_id, str) or not work_id
                or not isinstance(title, str) or not title.strip()
                or not isinstance(summary, str) or not summary.strip()
                or type(fulltext) is not bool):
            raise ValueError(f"Metadata sách sai hoặc book_id trùng ở dòng {line_number}")
        authors = raw.get("authors")
        genres = raw.get("genres")
        topics = raw.get("topics")
        if (not isinstance(authors, list) or not authors or not all(isinstance(x, str) for x in authors)
                or not isinstance(genres, list) or not all(isinstance(x, str) for x in genres)
                or not isinstance(topics, list) or not all(isinstance(x, str) for x in topics)):
            raise ValueError(f"Danh sách authors/genres/topics sai ở dòng {line_number}")
        sources = raw.get("sources")
        if not isinstance(sources, list) or not sources or not all(isinstance(x, dict) for x in sources):
            raise ValueError(f"Sách thiếu sources ở dòng {line_number}")
        statuses = sorted({
            source.get("rights_status", "unknown")
            for source in sources
            if isinstance(source.get("rights_status", "unknown"), str)
        })
        summary_sources = [source for source in sources if source.get("content_type") == "summary"]
        summary_url = summary_sources[0].get("source_url", "") if summary_sources else ""
        if not isinstance(summary_url, str):
            raise ValueError(f"summary source URL sai ở dòng {line_number}")
        books.append(BM25Book(
            book_id=book_id,
            work_id=work_id,
            title=title,
            authors=tuple(authors),
            genres=tuple(genres),
            topics=tuple(topics),
            summary=summary,
            has_fulltext=fulltext,
            source_rights_status=";".join(statuses) if statuses else "unknown",
            summary_source_url=summary_url,
            text=build_book_text(raw, genre_labels, topic_labels),
        ))
        seen.add(book_id)
    return books, genre_labels, topic_labels


def _query_terms(query: str) -> Counter[str]:
    if not isinstance(query, str):
        raise ValueError("q phải là chuỗi")
    normalized = unicodedata.normalize("NFC", query).strip()
    if not normalized or len(normalized) > 500:
        raise ValueError("q phải dài từ 1 đến 500 ký tự sau NFC và trim")
    return Counter(tokenize(normalized))


def _filter_values(filters: Mapping[str, object] | None) -> tuple[set[str], set[str], bool | None]:
    if filters is None:
        filters = {}
    if not isinstance(filters, Mapping):
        raise ValueError("filters phải là object")
    unexpected = set(filters) - {"authors", "genres", "has_fulltext"}
    if unexpected:
        raise ValueError(f"Filter không hỗ trợ: {sorted(unexpected)}")

    def values(field: str, *, normalize_authors: bool) -> set[str]:
        items = filters.get(field, [])
        if not isinstance(items, (list, tuple)) or len(items) > 20:
            raise ValueError(f"filters.{field} phải là danh sách tối đa 20 giá trị")
        if not all(isinstance(item, str) and item for item in items):
            raise ValueError(f"filters.{field} chỉ nhận chuỗi không rỗng")
        if normalize_authors:
            return {normalize_metadata_text(item) for item in items}
        return set(items)

    fulltext = filters.get("has_fulltext")
    if fulltext is not None and type(fulltext) is not bool:
        raise ValueError("filters.has_fulltext phải là boolean hoặc null")
    return values("authors", normalize_authors=True), values("genres", normalize_authors=False), fulltext


class BM25Index:
    """In-memory BM25 ranking over edition-level books in one chosen corpus."""

    def __init__(
        self,
        books: Iterable[BM25Book],
        *,
        genre_codes: Iterable[str] | None = None,
        k1: float = K1,
        b: float = B,
    ) -> None:
        if type(k1) not in {int, float} or not math.isfinite(k1) or k1 <= 0:
            raise ValueError("k1 phải là số hữu hạn lớn hơn 0")
        if type(b) not in {int, float} or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("b phải nằm trong [0, 1]")
        self.k1 = float(k1)
        self.b = float(b)
        self.documents = tuple(books)
        self._by_id = {book.book_id: book for book in self.documents}
        if len(self._by_id) != len(self.documents):
            raise ValueError("book_id trùng trong corpus BM25")
        self.genre_codes = set(genre_codes) if genre_codes is not None else {
            genre for book in self.documents for genre in book.genres
        }
        self._term_frequencies = {
            book.book_id: Counter(tokenize(book.text)) for book in self.documents
        }
        self._lengths = {book.book_id: sum(self._term_frequencies[book.book_id].values())
                         for book in self.documents}
        self._document_frequencies: Counter[str] = Counter()
        for frequencies in self._term_frequencies.values():
            self._document_frequencies.update(frequencies.keys())
        self.document_count = len(self.documents)
        self.average_document_length = (
            sum(self._lengths.values()) / self.document_count if self.document_count else 0.0
        )

    def idf(self, term: str) -> float:
        document_frequency = self._document_frequencies.get(term, 0)
        return math.log(1 + (self.document_count - document_frequency + 0.5)
                        / (document_frequency + 0.5))

    def _eligible(self, filters: Mapping[str, object] | None) -> list[BM25Book]:
        authors, genres, has_fulltext = _filter_values(filters)
        unknown = genres - self.genre_codes
        if unknown:
            raise ValueError(f"Mã thể loại không tồn tại: {sorted(unknown)}")
        return [book for book in self.documents
                if (not authors or bool(authors.intersection(book.authors)))
                and (not genres or bool(genres.intersection(book.genres)))
                and (has_fulltext is None or book.has_fulltext is has_fulltext)]

    def eligible_count(self, filters: Mapping[str, object] | None = None) -> int:
        return len(self._eligible(filters))

    def score(self, query: str, book_id: str) -> float:
        query_frequencies = _query_terms(query)
        if book_id not in self._by_id:
            raise KeyError(book_id)
        return self._score_terms(query_frequencies, book_id)

    def _score_terms(self, query_frequencies: Counter[str], book_id: str) -> float:
        frequencies = self._term_frequencies[book_id]
        length = self._lengths[book_id]
        score = 0.0
        for term, query_frequency in query_frequencies.items():
            term_frequency = frequencies.get(term, 0)
            if term_frequency == 0:
                continue
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * length / self.average_document_length
            )
            score += query_frequency * self.idf(term) * (
                term_frequency * (self.k1 + 1) / denominator
            )
        return score

    def search(
        self,
        query: str,
        *,
        k: int = MAX_K,
        filters: Mapping[str, object] | None = None,
    ) -> list[BM25Hit]:
        if type(k) is not int or not 1 <= k <= MAX_K:
            raise ValueError(f"k phải là số nguyên từ 1 đến {MAX_K}")
        query_frequencies = _query_terms(query)
        candidates = self._eligible(filters)
        ranked = sorted(
            ((self._score_terms(query_frequencies, book.book_id), book) for book in candidates),
            key=lambda item: (-item[0], item[1].book_id),
        )[:k]
        return [BM25Hit(book=book, rank=rank, score=score)
                for rank, (score, book) in enumerate(ranked, 1)]
