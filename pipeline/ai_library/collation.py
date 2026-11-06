from __future__ import annotations

import unicodedata
from typing import Tuple, Any

try:
    import icu  # type: ignore

    def _create_icu_collator() -> Any:
        """Tạo PyICU Collator theo Mục 10.4:
        Locale vi_VN, strength SECONDARY, normalization ON, numeric collation OFF,
        alternate handling NON_IGNORABLE.
        """
        collator = icu.Collator.createInstance(icu.Locale("vi_VN"))  # type: ignore
        collator.setStrength(icu.Collator.SECONDARY)  # type: ignore
        collator.setAttribute(icu.UCollAttribute.NORMALIZATION_MODE, icu.UCollAttributeValue.ON)  # type: ignore
        collator.setAttribute(icu.UCollAttribute.NUMERIC_COLLATION, icu.UCollAttributeValue.OFF)  # type: ignore
        collator.setAttribute(icu.UCollAttribute.ALTERNATE_HANDLING, icu.UCollAttributeValue.NON_IGNORABLE)  # type: ignore
        return collator

    _COLLATOR: Any = _create_icu_collator()

    def generate_title_sort_key(title: str) -> bytes:
        """Tạo sort key nhị phân từ tiêu đề sách đã chuẩn hóa."""
        norm_title = unicodedata.normalize("NFC", title.strip())
        return bytes(_COLLATOR.getSortKey(norm_title))

    def get_icu_versions() -> Tuple[str, str]:
        """Lấy phiên bản ICU và CLDR."""
        icu_ver = getattr(icu, "ICU_VERSION", "unknown")
        cldr_ver = getattr(icu, "CLDR_VERSION", "unknown")
        return str(icu_ver), str(cldr_ver)

except (ImportError, Exception):
    # Fallback chuẩn Unicode NFC UTF-8 nếu máy dev chưa cài libicu-dev/PyICU
    def generate_title_sort_key(title: str) -> bytes:
        norm_title = unicodedata.normalize("NFC", title.strip().lower())
        return norm_title.encode("utf-8")

    def get_icu_versions() -> Tuple[str, str]:
        return "fallback", "fallback"
