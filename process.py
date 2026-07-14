"""
process.py — Bước 2: Xử lý dữ liệu thô → tạo file phân tích
=============================================================
Chạy:  python process.py
Input:  data/raw_reviews.csv
Output: data/analyzed_reviews.csv
        data/wordcloud_data.json
"""

import logging
import sys
import time
from pathlib import Path

import pandas as pd

# ── Setup logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("process")

# ── Đường dẫn ─────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
INPUT_PATH  = DATA_DIR / "raw_reviews.csv"
OUTPUT_CSV  = DATA_DIR / "analyzed_reviews.csv"

# ── Thêm src/ vào sys.path ────────────────────────────────────────────────────
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from preprocess   import run as run_preprocess
from sentiment    import run as run_sentiment
from topic        import run as run_topic
from wordcloud_gen import run as run_wordcloud


def main():
    t_start = time.time()

    print("=" * 60)
    print("  PROCESS — Pipeline Xử Lý Dữ Liệu Review")
    print(f"  Input : {INPUT_PATH}")
    print(f"  Output: {OUTPUT_CSV}")
    print("=" * 60)

    # ── Kiểm tra file đầu vào ─────────────────────────────────────────────────
    if not INPUT_PATH.exists():
        print(f"\n  ✗ Không tìm thấy file: {INPUT_PATH}")
        print("  → Hãy chạy 'python scraper.py' trước.")
        sys.exit(1)

    # ── Đọc dữ liệu thô ──────────────────────────────────────────────────────
    print(f"\n[1/4] Đọc dữ liệu từ: {INPUT_PATH}")
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", low_memory=False)
    print(f"      → {len(df):,} dòng, {df.shape[1]} cột")

    # ── Bước 1: Tiền xử lý ───────────────────────────────────────────────────
    print("\n[2/4] Tiền xử lý văn bản (preprocess)...")
    df = run_preprocess(df)

    # ── Bước 2: Phân tích cảm xúc ────────────────────────────────────────────
    print("\n[3/4] Phân tích cảm xúc (sentiment)...")
    df = run_sentiment(df, use_model=False)

    # ── Bước 3: Phân loại chủ đề & vấn đề lỗi ───────────────────────────────
    print("\n[4/4] Phân loại chủ đề & vấn đề lỗi (topic)...")
    df = run_topic(df)

    # ── Lưu CSV phân tích ────────────────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n   Đã lưu {len(df):,} dòng → '{OUTPUT_CSV}'")

    # ── Sinh dữ liệu Word Cloud ──────────────────────────────────────────────
    print("\n[+] Sinh dữ liệu Word Cloud...")
    run_wordcloud(df, DATA_DIR)

    elapsed = time.time() - t_start
    print("=" * 60)
    print(f"  Hoàn tất pipeline trong {elapsed:.1f}s")
    print(f"  File CSV   : {OUTPUT_CSV}")
    print(f"  File WC    : {DATA_DIR / 'wordcloud_data.json'}")
    print("=" * 60)
    print("\nBước tiếp theo: Mở dashboard/index.html và upload 2 file trên.")


if __name__ == "__main__":
    main()
