"""
src/wordcloud_gen.py — Sinh dữ liệu Word Cloud (đổi tên để tránh conflict với thư viện wordcloud)
==================================================================================================
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer


def get_top_words(df: pd.DataFrame, limit: int = 100) -> list[dict]:
    """
    Trích xuất cụm từ phổ biến nhất (N-grams) cùng tần suất và cảm xúc chủ đạo.
    Sử dụng CountVectorizer của scikit-learn với thuật toán ma trận thưa.
    """
    if df is None or len(df) == 0:
        return []

    # Chọn cột văn bản phù hợp
    text_candidates = ["processed_text", "Nội dung sạch", "Nội dung review"]
    text_col = next((c for c in text_candidates if c in df.columns), None)
    if text_col is None:
        return []

    # Đảm bảo có cột sentiment
    if "sentiment" not in df.columns:
        df = df.copy()
        df["sentiment"] = "Neutral"

    valid_df = df[[text_col, "sentiment"]].dropna().copy()
    valid_df[text_col] = valid_df[text_col].astype(str).str.lower().str.strip()
    if len(valid_df) == 0:
        return []

    # Stopwords tiếng Việt
    vietnamese_stopwords = {
        "và", "của", "được", "cho", "ra", "với", "trong", "đến",
        "các", "những", "là", "có", "cũng", "đã", "đang",
        "sẽ", "phải", "lại", "này", "thế", "cái", "con",
        "nó", "chúng", "tôi", "bạn", "nào", "gì", "ở",
        "từ", "vào", "lên", "về", "như", "thì", "mà",
        "nên", "sự", "nhất", "app", "ứng_dụng",
        "ngân_hàng", "bank", "mobile", "banking",
        "ibanking", "ok", "tốt", "nhanh", "dùng"
    }

    # Trích xuất cụm từ (ngram 2-3)
    try:
        vectorizer = CountVectorizer(
            token_pattern=r"(?u)\b[\w_]+\b",
            ngram_range=(2, 3),
            stop_words=list(vietnamese_stopwords),
            min_df=3,
            max_features=500
        )
        X = vectorizer.fit_transform(valid_df[text_col])
        phrases = vectorizer.get_feature_names_out()
        counts = np.asarray(X.sum(axis=0)).flatten()
    except ValueError:
        return []

    # Phân loại cảm xúc cho từng cụm từ (Vectorized)
    sentiments = valid_df["sentiment"].str.title().values
    pos_mask = (sentiments == "Positive")
    neg_mask = (sentiments == "Negative")
    neu_mask = ~(pos_mask | neg_mask)

    pos_counts = np.asarray(X[pos_mask].sum(axis=0)).flatten()
    neg_counts = np.asarray(X[neg_mask].sum(axis=0)).flatten()
    neu_counts = np.asarray(X[neu_mask].sum(axis=0)).flatten()

    # Sắp xếp lấy Top
    sorted_items = sorted(
        zip(phrases, counts, range(len(phrases))),
        key=lambda x: x[1],
        reverse=True
    )[:limit]

    results = []
    for phrase, count, idx in sorted_items:
        p_val = pos_counts[idx]
        n_val = neg_counts[idx]
        neu_val = neu_counts[idx]

        dominant = "Neutral"
        max_val = neu_val
        if p_val > max_val:
            dominant = "Positive"
            max_val = p_val
        if n_val > max_val:
            dominant = "Negative"

        results.append({
            "text":      phrase.replace("_", " "),
            "value":     int(count),
            "sentiment": dominant,
        })

    return results


def run(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    """
    Tính toán word cloud cho từng ngân hàng và phân khúc.
    Lưu kết quả vào output_dir/wordcloud_data.json.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    wc_data: dict = {}

    banks = df["Tên ngân hàng"].dropna().unique() if "Tên ngân hàng" in df.columns else []

    for bank in banks:
        bank_df = df[df["Tên ngân hàng"] == bank]
        seg_col = "Phân khúc KH"
        wc_data[bank] = {
            "all":    get_top_words(bank_df, limit=100),
            "retail": get_top_words(
                bank_df[bank_df[seg_col] == "Cá nhân"] if seg_col in bank_df.columns else bank_df,
                limit=100
            ),
            "efast":  get_top_words(
                bank_df[bank_df[seg_col] == "Doanh nghiệp"] if seg_col in bank_df.columns else bank_df,
                limit=100
            ),
        }

    # Thêm mục "Tất cả ngân hàng"
    seg_col = "Phân khúc KH"
    wc_data["All"] = {
        "all":    get_top_words(df, limit=100),
        "retail": get_top_words(
            df[df[seg_col] == "Cá nhân"] if seg_col in df.columns else df,
            limit=100
        ),
        "efast":  get_top_words(
            df[df[seg_col] == "Doanh nghiệp"] if seg_col in df.columns else df,
            limit=100
        ),
    }

    # Ghi file JSON an toàn (ghi vào file tạm rồi dùng os.replace)
    output_path = output_dir / "wordcloud_data.json"
    temp_path   = output_dir / "wordcloud_data.json.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(wc_data, f, ensure_ascii=False, indent=2)
        if temp_path.exists():
            os.replace(str(temp_path), str(output_path))
        print(f"[WordCloud] Đã xuất dữ liệu tại: {output_path}")
    except Exception as e:
        print(f"[WordCloud] Lỗi khi ghi file: {e}")

    return df
