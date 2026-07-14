"""
src/sentiment.py — Phân tích cảm xúc (Positive / Negative / Neutral)
======================================================================
Tầng 1: Rule-based Hybrid (Rating + Keyword regex + phủ định)
Tầng 2: PhoBERT (wonrax/phobert-base-vietnamese-sentiment) — tùy chọn
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata

import pandas as pd

log = logging.getLogger(__name__)


# ── Hàm chuẩn hóa bỏ dấu tiếng Việt ─────────────────────────────────────────
def _remove_accents(input_str: str) -> str:
    if not isinstance(input_str, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", input_str)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.replace("đ", "d").replace("Đ", "D").lower()


# ── Bộ từ điển từ khóa ────────────────────────────────────────────────────────
_NEGATIVE_WORDS_RAW = [
    "tệ", "te", "lỗi", "loi", "chán", "chan", "khó", "kho", "chậm", "cham",
    "lag", "đơ", "do", "treo", "bực", "buc", "tức", "tuc", "phiền", "phien",
    "rắc rối", "rac roi", "rườm rà", "ruom ra", "khó chịu", "kho chiu",
    "thất vọng", "that vong", "tệ hại", "te hai", "không được", "khong duoc",
    "ko được", "ko duoc", "k được", "k duoc", "xấu", "xau", "dở",
    "bất tiện", "bat tien", "phế", "phe", "cải lùi", "cai lui", "hỏng", "hong",
    "không vào được", "khong vao duoc", "ko vào được", "không đăng nhập", "khong dang nhap",
    "không chuyển được", "khong chuyen duoc", "không nhận", "khong nhan",
    "không gửi", "khong gui", "lừa đảo", "lua dao", "trừ tiền", "tru tien",
    "mất tiền", "mat tien", "đổi ngân hàng", "doi ngan hang",
    "lỗi app", "loi app", "văng", "vang", "giao dịch lỗi", "giao dich loi",
    "otp chậm", "otp cham", "mã không về", "ma khong ve",
    "không nhận otp", "khong nhan otp", "không ổn", "khong on",
    "không ok", "khong ok", "không hài lòng", "khong hai long",
    "bảo trì", "bao tri", "quá tệ", "qua te", "lỗi hệ thống", "loi he thong",
]

_POSITIVE_WORDS_RAW = [
    "tốt", "tot", "tuyệt vời", "tuyet voi", "tuyệt", "tuyet", "đẹp", "dep",
    "mượt", "muot", "nhanh", "tiện", "tien", "tiện lợi", "tien loi",
    "hài lòng", "hai long", "ok", "ổn", "on", "thích", "thich",
    "dễ dùng", "de dung", "dễ sử dụng", "de su dung", "an toàn", "an toan",
    "ổn định", "on dinh", "sịn", "sin", "hay", "xuất sắc", "xuat sac",
    "hoàn hảo", "hoan hao", "dùng tốt", "dung tot", "xài tốt", "xai tot",
    "ứng dụng tốt", "ung dung tot", "app tốt", "app tot",
    "chuyển tiền nhanh", "chuyen tien nhanh", "giao diện đẹp", "giao dien dep",
]

_NEGATION_PATS = [
    r"\bkhong\b", r"\bko\b", r"\bk\b", r"\bcha\b",
    r"\bchang\b", r"\bkhông\b", r"\bchả\b", r"\bchẳng\b",
]

# Compile regex trước
_NEG_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in _NEGATIVE_WORDS_RAW]
_POS_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in _POSITIVE_WORDS_RAW]


def _classify_sentiment_baseline(rating, clean_text: str) -> str:
    """Tầng 1: Rule-based kết hợp rating + keyword + phủ định."""
    if pd.isna(rating):
        return "Neutral"

    rating = int(rating)
    text_orig = str(clean_text).lower()
    text_no_accent = _remove_accents(text_orig)

    # Đếm từ khóa tiêu cực
    neg_count = 0
    for pat in _NEG_PATTERNS:
        if pat.search(text_orig) or pat.search(text_no_accent):
            neg_count += 1

    # Đếm từ khóa tích cực + lọc phủ định
    pos_count = 0
    for pat in _POS_PATTERNS:
        positions = [m.start() for m in pat.finditer(text_orig)]
        if not positions:
            positions = [m.start() for m in pat.finditer(text_no_accent)]
        for pos in positions:
            prefix = text_orig[max(0, pos - 15):pos]
            prefix_na = text_no_accent[max(0, pos - 15):pos]
            if any(
                re.search(np, prefix) or re.search(np, prefix_na)
                for np in _NEGATION_PATS
            ):
                neg_count += 1  # "không tốt" → tính là tiêu cực
            else:
                pos_count += 1

    # Quy tắc phân loại
    if rating <= 2:
        return "Negative"
    elif rating == 3:
        if neg_count > pos_count and neg_count >= 1:
            return "Negative"
        elif pos_count > neg_count and pos_count >= 1:
            return "Positive"
        return "Neutral"
    else:  # rating 4 hoặc 5
        if neg_count >= 3 and pos_count <= 1:
            return "Neutral"
        return "Positive"


def run(df: pd.DataFrame, use_model: bool | None = None) -> pd.DataFrame:
    """
    Nhận DataFrame đã preprocess → trả về DataFrame có thêm cột 'sentiment'.

    use_model=None  → đọc từ biến môi trường SENTIMENT_USE_MODEL (mặc định False)
    use_model=True  → thử dùng PhoBERT, fallback keyword nếu lỗi
    use_model=False → dùng keyword-based (nhanh, không cần GPU)
    """
    df = df.copy()

    if use_model is None:
        use_model = os.getenv("SENTIMENT_USE_MODEL", "false").lower() == "true"

    # Đảm bảo cột Rating là số
    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce").fillna(3).astype(int)

    clean_col = "Nội dung sạch" if "Nội dung sạch" in df.columns else "Nội dung review"

    model_ok = False
    if use_model:
        try:
            from transformers import AutoTokenizer, RobertaForSequenceClassification, pipeline

            model_name = "wonrax/phobert-base-vietnamese-sentiment"
            log.info("[Sentiment] Tải PhoBERT model: %s", model_name)
            mdl = RobertaForSequenceClassification.from_pretrained(model_name)
            tok = AutoTokenizer.from_pretrained(model_name, use_fast=False)
            clf = pipeline("sentiment-analysis", model=mdl, tokenizer=tok, device=-1, batch_size=32)

            texts = [str(t)[:250] if str(t).strip() else "ổn" for t in df[clean_col]]
            results = clf(texts)

            label_map = {"NEG": "Negative", "POS": "Positive", "NEU": "Neutral"}
            df["sentiment"] = [label_map.get(r["label"], "Neutral") for r in results]
            model_ok = True
            log.info("[Sentiment] ✅ Dùng PhoBERT")
        except ImportError:
            log.warning("[Sentiment] Thiếu thư viện PhoBERT → fallback keyword")
        except Exception as e:
            log.warning("[Sentiment] Không tải được model (%s) → fallback keyword", e)

    if not model_ok:
        log.info("[Sentiment] Dùng keyword-based (Tầng 1 nâng cao)")
        print("[Sentiment] Phân tích cảm xúc bằng rule-based...")
        df["sentiment"] = df.apply(
            lambda row: _classify_sentiment_baseline(
                row.get("Rating", 3), row.get(clean_col, "")
            ),
            axis=1,
        )

    dist = df["sentiment"].value_counts().to_dict()
    print(f"[Sentiment] Phân bổ: {dist}")
    return df
