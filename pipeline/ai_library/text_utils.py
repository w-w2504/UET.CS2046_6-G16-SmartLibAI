from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import List, Tuple, Dict, Any


def normalize_metadata_text(text: str) -> str:
    """Chuẩn hóa metadata theo Mục 9.4:
    NFC, trim hai đầu, gộp khoảng trắng liên tiếp thành một dấu cách, giữ nguyên chữ hoa/dấu.
    """
    if not text:
        return ""
    # Chuẩn hóa Unicode NFC
    norm = unicodedata.normalize("NFC", text)
    # Gộp khoảng trắng (space, tab, non-breaking space...) thành 1 khoảng trắng duy nhất
    norm = re.sub(r"\s+", " ", norm)
    return norm.strip()


def normalize_fulltext_content(text: str) -> str:
    """Chuẩn hóa toàn văn chương/đoạn theo Mục 9.4:
    CRLF/CR -> LF, NFC, bỏ khoảng trắng cuối dòng, trim hai đầu; giữ khoảng trắng nội bộ và dấu câu.
    """
    if not text:
        return ""
    # Chuyển CRLF và CR thành LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Chuẩn hóa Unicode NFC
    text = unicodedata.normalize("NFC", text)
    # Tách dòng để loại bỏ khoảng trắng cuối dòng và trim
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
    return "\n".join(lines).strip()


def compute_sha256(text: str) -> str:
    """Tính SHA-256 của byte UTF-8 sau chuẩn hóa (hex chữ thường) theo Mục 9.4."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest().lower()


def generate_chunk_id(book_id: str, chapter_id: str, char_start: int, char_end: int, text: str) -> str:
    """chunk_id là K_ ghép SHA-256 của book_id, chapter_id, offset và text theo Mục 3.1 & 11.3."""
    payload = {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "char_start": char_start,
        "char_end": char_end,
        "text": text,
    }
    canonical_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    h = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest().lower()
    return f"K_{h}"


def split_sentences_vietnamese(paragraph_text: str) -> List[str]:
    """Tách đoạn thành các câu theo dấu . ! ? … khi tiếp theo là khoảng trắng hoặc hết đoạn.
    Giữ nguyên dấu đóng ngoặc/nháy liền sau dấu câu theo Mục 11.3.
    """
    if not paragraph_text:
        return []

    # Regex nhận diện ranh giới câu: dấu câu (. ! ? …) kèm theo ngoặc kép/đơn/ngoặc đơn nếu có
    # theo sau bởi khoảng trắng hoặc kết thúc chuỗi
    pattern = r"(?<=[.!?…][\"')\]]?)\s+"
    parts = re.split(pattern, paragraph_text)
    return [p.strip() for p in parts if p.strip()]


class TextTokenizerHelper:
    """Bộ đếm token tuân thủ encoder intfloat/multilingual-e5-small theo Mục 10.4 & 11.3.
    Hỗ trợ fallback đếm gần đúng nếu môi trường chưa nạp transformer model.
    """

    def __init__(self, tokenizer: Any = None):
        self._tokenizer = tokenizer

    def count_tokens(self, text: str, prefix: str = "passage: ") -> int:
        full_text = f"{prefix}{text}"
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(full_text, add_special_tokens=True))
        # Dự phòng đếm token xấp xỉ cho tiếng Việt (trung bình ~1.3 token / từ đối với xlm-roberta)
        words = full_text.split()
        return max(1, int(len(words) * 1.3) + 2)


def chunk_chapter(
    book_id: str,
    chapter_id: str,
    chapter_text: str,
    paragraphs: List[Dict[str, Any]],
    tokenizer_helper: TextTokenizerHelper | None = None,
    max_content_tokens: int = 400,
    max_total_tokens: int = 480,
    max_overlap_tokens: int = 60,
) -> List[Dict[str, Any]]:
    """Thuật toán chia chunk xác định theo Mục 11.3:
    - Xử lý từng chương theo order_no.
    - Đơn vị ban đầu là đoạn nguyên vẹn (paragraph).
    - Đoạn > 400 token nội dung được tách theo câu.
    - Gom tham lam các đơn vị liên tiếp sao cho content <= 400 token và total <= 480 token.
    - Chồng lặp tối đa 60 token bằng câu/đoạn hoàn chỉnh của chunk trước.
    - Offset [char_start, char_end) tính theo Unicode code point trên toàn văn chương.
    """
    if tokenizer_helper is None:
        tokenizer_helper = TextTokenizerHelper()

    # 1. Chuẩn bị các đơn vị cơ sở (Units): tách câu nếu đoạn quá dài
    units: List[Dict[str, Any]] = []
    for p in paragraphs:
        p_text = p["text"]
        p_order = p["order_no"]
        p_start = p["char_start"]

        tokens = tokenizer_helper.count_tokens(p_text, prefix="")
        if tokens <= max_content_tokens:
            units.append({
                "text": p_text,
                "paragraph_order": p_order,
                "char_start": p_start,
                "char_end": p["char_end"],
                "token_count": tokens,
            })
        else:
            # Tách đoạn thành các câu
            sentences = split_sentences_vietnamese(p_text)
            curr_pos = p_start
            for s in sentences:
                s_idx = chapter_text.find(s, curr_pos)
                if s_idx == -1:
                    s_idx = curr_pos
                s_end = s_idx + len(s)
                s_tokens = tokenizer_helper.count_tokens(s, prefix="")
                units.append({
                    "text": s,
                    "paragraph_order": p_order,
                    "char_start": s_idx,
                    "char_end": s_end,
                    "token_count": s_tokens,
                })
                curr_pos = s_end

    if not units:
        return []

    # 2. Gom tham lam các chunk kèm overlap
    chunks: List[Dict[str, Any]] = []
    i = 0
    num_units = len(units)

    while i < num_units:
        chunk_units: List[Dict[str, Any]] = []
        current_content_tokens = 0

        # Thêm overlap từ chunk trước nếu có (tối đa 60 token)
        if chunks:
            prev_chunk_units = chunks[-1]["_units"]
            overlap_units: List[Dict[str, Any]] = []
            overlap_tokens = 0
            for u in reversed(prev_chunk_units):
                if overlap_tokens + u["token_count"] <= max_overlap_tokens:
                    overlap_units.insert(0, u)
                    overlap_tokens += u["token_count"]
                else:
                    break
            
            # Chỉ mang overlap nếu còn chỗ cho ít nhất 1 unit mới
            if overlap_tokens + units[i]["token_count"] <= max_content_tokens:
                chunk_units.extend(overlap_units)
                current_content_tokens += overlap_tokens

        # Gom các unit mới chưa phủ
        added_new = 0
        while i < num_units:
            u = units[i]
            if current_content_tokens + u["token_count"] <= max_content_tokens or added_new == 0:
                chunk_units.append(u)
                current_content_tokens += u["token_count"]
                i += 1
                added_new += 1
            else:
                break

        # Xác định phạm vi text và offset thực tế trên văn bản chương
        start_char = chunk_units[0]["char_start"]
        end_char = chunk_units[-1]["char_end"]
        # Lát cắt chuẩn xác từ văn bản chương đã chuẩn hóa
        chunk_slice_text = chapter_text[start_char:end_char]
        
        para_start = chunk_units[0]["paragraph_order"]
        para_end = chunk_units[-1]["paragraph_order"]
        total_tokens = tokenizer_helper.count_tokens(chunk_slice_text, prefix="passage: ")
        
        cid = generate_chunk_id(book_id, chapter_id, start_char, end_char, chunk_slice_text)
        chash = compute_sha256(chunk_slice_text)

        chunks.append({
            "chunk_id": cid,
            "book_id": book_id,
            "chapter_id": chapter_id,
            "paragraph_start": para_start,
            "paragraph_end": para_end,
            "char_start": start_char,
            "char_end": end_char,
            "text": chunk_slice_text,
            "token_count": total_tokens,
            "content_hash": chash,
            "_units": chunk_units,
        })

    # Xóa thuộc tính phụ _units trước khi trả về
    for c in chunks:
        c.pop("_units", None)

    return chunks

