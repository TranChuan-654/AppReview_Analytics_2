"""
src/preprocess.py — Tiền xử lý văn bản tiếng Việt
===================================================
"""
from __future__ import annotations

import os
import re
import string
import unicodedata
from multiprocessing import Pool, cpu_count

import pandas as pd

try:
    from underthesea import word_tokenize
except ImportError:
    word_tokenize = None


# ── Hàm loại bỏ Emoji ─────────────────────────────────────────────────────────
def _remove_emoji(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u200d\u2640-\u2642\u2600-\u2B55\u23cf\u23e9\u231a\u3030\ufe0f"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(" ", text)


# ── Rút gọn ký tự kéo dài ─────────────────────────────────────────────────────
def _reduce_repeated(text: str) -> str:
    return re.sub(r"([a-zA-Z])\1{2,}", r"\1", text)


# ── Loại bỏ URL / email ───────────────────────────────────────────────────────
def _remove_links(text: str) -> str:
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"\S+@\S+", "", text)
    return text


# ── Pipeline tiền xử lý tổng hợp ─────────────────────────────────────────────
def preprocess_text(text) -> tuple[str, str]:
    """
    Trả về (clean_text, processed_text).
    clean_text    : văn bản sạch (không dấu câu, không emoji, chuẩn hóa unicode)
    processed_text: văn bản đã tách từ tiếng Việt (underthesea word_tokenize)
    """
    if not text or str(text).strip() == "":
        return "", ""

    text = str(text).lower()
    text = _remove_emoji(text)
    text = _remove_links(text)
    text = _reduce_repeated(text)

    # Định dạng khoảng trắng quanh dấu câu
    text = re.sub(r"(\w)\s*([" + string.punctuation + r"])\s*(\w)", r"\1 \2 \3", text)
    text = re.sub(r"(\w)\s*([" + string.punctuation + r"])", r"\1 \2", text)
    text = re.sub(f"([{string.punctuation}])([{string.punctuation}])+", r"\1", text)

    text = text.strip()
    while text and text[-1] in string.punctuation + string.whitespace:
        text = text[:-1]
    while text and text[0] in string.punctuation + string.whitespace:
        text = text[1:]

    text_no_punc = text.translate(str.maketrans("", "", string.punctuation))
    clean_text = " ".join(text_no_punc.split())
    clean_text = unicodedata.normalize("NFKC", clean_text)

    if word_tokenize is not None:
        try:
            processed_text = word_tokenize(clean_text, format="text")
        except Exception:
            processed_text = clean_text.replace(" ", "_")
    else:
        processed_text = clean_text.replace(" ", "_")

    return clean_text, processed_text


def _preprocess_worker(text) -> tuple[str, str]:
    """Wrapper dùng trong multiprocessing (phải là top-level function)."""
    return preprocess_text(text)


def run(df: pd.DataFrame, use_tokenize: bool = True, n_workers: int = 0) -> pd.DataFrame:
    """
    Nhận DataFrame thô → trả về DataFrame đã tiền xử lý.
    Thêm cột: 'Nội dung sạch', 'processed_text', các cột thời gian phái sinh.

    Args:
        use_tokenize: Bật underthesea word_tokenize (chậm hơn ~10×, cần cài underthesea).
                      False (mặc định) = dùng clean_text trực tiếp, nhanh hơn nhiều.
        n_workers   : Số worker multiprocessing. 0 = tự động (cpu_count // 2).
    """
    df = df.copy()

    # ── Chuẩn hóa tên cột ─────────────────────────────────────────────────────
    _COL_MAP = {
        "Ten ngan hang":    "Tên ngân hàng",
        "Ten app":          "Tên app",
        "Nguon review":     "Nguồn review",
        "Noi dung review":  "Nội dung review",
        "Thoi gian review": "Thời gian review",
        "So luot huu ich":  "Số lượt hữu ích",
        "bank_name":        "Tên ngân hàng",
        "app_name":         "Tên app",
        "content":          "Nội dung review",
        "score":            "Rating",
        "at":               "Thời gian review",
        "userName":         "Username",
    }
    rename = {
        old: new for old, new in _COL_MAP.items()
        if old in df.columns and new not in df.columns
    }
    if rename:
        df = df.rename(columns=rename)

    # ── Làm sạch cơ bản ───────────────────────────────────────────────────────
    df = df.dropna(subset=["Nội dung review"])
    df["Username"] = df.get(
        "Username", pd.Series("Ẩn danh", index=df.index)
    ).fillna("Ẩn danh")
    if "Version app" in df.columns:
        df["Version app"] = df["Version app"].fillna("unknown")

    # Chuẩn hóa kiểu thời gian
    df["Thời gian review"] = pd.to_datetime(df["Thời gian review"], errors="coerce")
    df = df.dropna(subset=["Thời gian review"])

    # Lọc trùng
    df = df.drop_duplicates(subset=["Nội dung review", "Username"]).copy()

    # Lọc từ 2023 trở đi
    df = df[df["Thời gian review"] >= "2023-01-01"].copy()

    # Cột thời gian phái sinh
    df["Năm review"]       = df["Thời gian review"].dt.year
    df["Tháng review"]     = df["Thời gian review"].dt.month
    df["Quý review"]       = df["Thời gian review"].dt.quarter
    df["Tháng-năm review"] = df["Thời gian review"].dt.to_period("M").astype(str)
    df["Quý-năm review"]   = (
        df["Năm review"].astype(str) + "-Q" + df["Quý review"].astype(str)
    )

    df = df.reset_index(drop=True)

    # ── Tiền xử lý văn bản ────────────────────────────────────────────────────
    n = len(df)
    texts = df["Nội dung review"].tolist()

    if use_tokenize and word_tokenize is not None:
        # Song song hóa bằng multiprocessing
        workers = n_workers or max(1, cpu_count() // 2)
        chunk = max(1, n // (workers * 4))   # chunksize tối ưu
        print(f"[Preprocess] word_tokenize {n:,} dòng | {workers} workers | chunk={chunk}")
        with Pool(processes=workers) as pool:
            results = []
            done = 0
            for pair in pool.imap(_preprocess_worker, texts, chunksize=chunk):
                results.append(pair)
                done += 1
                if done % 10000 == 0:
                    print(f"  → {done:,}/{n:,} ({done*100//n}%)")
        clean_list = [r[0] for r in results]
        proc_list  = [r[1] for r in results]
    else:
        # Nhanh: chỉ dùng clean_text, bỏ qua word_tokenize
        if use_tokenize and word_tokenize is None:
            print("[Preprocess] ⚠ underthesea không khả dụng → dùng chế độ nhanh")
        print(f"[Preprocess] Làm sạch {n:,} dòng (chế độ nhanh, không word_tokenize)...")
        clean_list, proc_list = [], []
        BATCH = 50_000
        for i in range(0, n, BATCH):
            batch = texts[i:i+BATCH]
            for text in batch:
                c, _ = preprocess_text(text)
                clean_list.append(c)
                proc_list.append(c)   # processed_text = clean_text khi không tokenize
            print(f"  → {min(i+BATCH, n):,}/{n:,} ({min(i+BATCH, n)*100//n}%)")

    df["Nội dung sạch"]  = clean_list
    df["processed_text"] = proc_list

    # Loại review quá ngắn sau khi làm sạch (< 2 ký tự)
    df = df[df["Nội dung sạch"].astype(str).str.len() >= 2].copy()
    df = df.reset_index(drop=True)

    print(f"[Preprocess] Hoàn thành: {len(df):,} dòng")
    return df
