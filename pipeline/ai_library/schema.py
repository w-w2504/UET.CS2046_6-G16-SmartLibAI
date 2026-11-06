import sqlite3
from pathlib import Path

DDL_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS works (
    snapshot_id TEXT NOT NULL,
    work_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, work_id)
);

CREATE TABLE IF NOT EXISTS books (
    snapshot_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    work_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_sort_key BLOB NOT NULL,
    summary TEXT NOT NULL,
    language TEXT NOT NULL CHECK(language = 'vi'),
    has_fulltext INTEGER NOT NULL CHECK(has_fulltext IN (0, 1)),
    cover_url TEXT,
    PRIMARY KEY (snapshot_id, book_id),
    FOREIGN KEY (snapshot_id, work_id) REFERENCES works (snapshot_id, work_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_authors (
    snapshot_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    order_no INTEGER NOT NULL CHECK(order_no >= 1),
    author_name TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, book_id, order_no),
    FOREIGN KEY (snapshot_id, book_id) REFERENCES books (snapshot_id, book_id) ON DELETE CASCADE,
    UNIQUE (snapshot_id, book_id, author_name)
);

CREATE TABLE IF NOT EXISTS taxonomy (
    snapshot_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('genre', 'topic')),
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, kind, code)
);

CREATE TABLE IF NOT EXISTS book_labels (
    snapshot_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    code TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, book_id, kind, code),
    FOREIGN KEY (snapshot_id, book_id) REFERENCES books (snapshot_id, book_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id, kind, code) REFERENCES taxonomy (snapshot_id, kind, code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
    snapshot_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK(content_type IN ('metadata', 'summary', 'cover', 'fulltext')),
    source_url TEXT NOT NULL,
    source_note TEXT NOT NULL,
    rights_status TEXT NOT NULL CHECK(rights_status IN ('approved', 'pending', 'rejected')),
    rights_note TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    PRIMARY KEY (snapshot_id, source_id),
    FOREIGN KEY (snapshot_id, book_id) REFERENCES books (snapshot_id, book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chapters (
    snapshot_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    order_no INTEGER NOT NULL CHECK(order_no >= 1),
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, chapter_id),
    FOREIGN KEY (snapshot_id, book_id) REFERENCES books (snapshot_id, book_id) ON DELETE CASCADE,
    UNIQUE (snapshot_id, book_id, order_no)
);

CREATE TABLE IF NOT EXISTS paragraphs (
    snapshot_id TEXT NOT NULL,
    paragraph_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    order_no INTEGER NOT NULL CHECK(order_no >= 1),
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL CHECK(char_start >= 0),
    char_end INTEGER NOT NULL CHECK(char_end > char_start),
    PRIMARY KEY (snapshot_id, paragraph_id),
    FOREIGN KEY (snapshot_id, chapter_id) REFERENCES chapters (snapshot_id, chapter_id) ON DELETE CASCADE,
    UNIQUE (snapshot_id, chapter_id, order_no)
);

CREATE TABLE IF NOT EXISTS chunks (
    snapshot_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    paragraph_start INTEGER NOT NULL,
    paragraph_end INTEGER NOT NULL,
    char_start INTEGER NOT NULL CHECK(char_start >= 0),
    char_end INTEGER NOT NULL CHECK(char_end > char_start),
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK(token_count >= 1),
    content_hash TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, chunk_id),
    FOREIGN KEY (snapshot_id, chapter_id) REFERENCES chapters (snapshot_id, chapter_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id, book_id) REFERENCES books (snapshot_id, book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vector_mapping (
    snapshot_id TEXT NOT NULL,
    index_name TEXT NOT NULL,
    row_id INTEGER NOT NULL CHECK(row_id >= 0),
    object_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, index_name, row_id),
    UNIQUE (snapshot_id, index_name, object_id)
);

-- Chỉ mục hỗ trợ truy vấn nhanh
CREATE INDEX IF NOT EXISTS idx_books_work ON books (snapshot_id, work_id);
CREATE INDEX IF NOT EXISTS idx_book_labels_code ON book_labels (snapshot_id, kind, code);
CREATE INDEX IF NOT EXISTS idx_chapters_book_order ON chapters (snapshot_id, book_id, order_no);
CREATE INDEX IF NOT EXISTS idx_paragraphs_chapter_order ON paragraphs (snapshot_id, chapter_id, order_no);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks (snapshot_id, book_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks (snapshot_id, chapter_id);
"""

def init_database(db_path: Path | str) -> sqlite3.Connection:
    """Khởi tạo cơ sở dữ liệu SQLite với schema hoàn chỉnh theo Mục 9.3."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(DDL_SQL)
    conn.commit()
    return conn

