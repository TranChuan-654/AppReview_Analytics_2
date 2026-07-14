"""
scraper.py — Bước 1: Cào đánh giá ứng dụng từ Google Play
===========================================================
Chạy:  python scraper.py
Output: data/raw_reviews.csv
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

# ── Unbuffered output để log real-time ────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

# ==============================================================================
# 1. DANH SÁCH ỨNG DỤNG NGÂN HÀNG
# ==============================================================================

BANK_APPS = [
    # ── Khách hàng Cá nhân ──────────────────────────────────────────────────
    {
        "bank_name":     "VietinBank",
        "app_name":      "VietinBank iPay",
        "app_id":        "com.vietinbank.ipay",
        "customer_type": "Cá nhân",
    },
    {
        "bank_name":     "Agribank",
        "app_name":      "Agribank Plus",
        "app_id":        "com.vnpay.Agribank3g",
        "customer_type": "Cá nhân",
    },
    {
        "bank_name":     "Vietcombank",
        "app_name":      "VCB Digibank",
        "app_id":        "com.VCB",
        "customer_type": "Cá nhân",
    },
    {
        "bank_name":     "BIDV",
        "app_name":      "BIDV SmartBanking",
        "app_id":        "com.vnpay.bidv",
        "customer_type": "Cá nhân",
    },
    {
        "bank_name":     "Techcombank",
        "app_name":      "Techcombank Mobile",
        "app_id":        "vn.com.techcombank.bb.app",
        "customer_type": "Cá nhân",
    },
    {
        "bank_name":     "MB Bank",
        "app_name":      "MB Bank",
        "app_id":        "com.mbmobile",
        "customer_type": "Cá nhân",
    },
    # ── Khách hàng Doanh nghiệp ─────────────────────────────────────────────
    {
        "bank_name":     "Agribank",
        "app_name":      "Agribank Corporate eBanking",
        "app_id":        "vn.com.agribank.ebanking.cu",
        "customer_type": "Doanh nghiệp",
    },
    {
        "bank_name":     "Vietcombank",
        "app_name":      "VCB DigiBiz",
        "app_id":        "com.vcb.sme",
        "customer_type": "Doanh nghiệp",
    },
    {
        "bank_name":     "BIDV",
        "app_name":      "BIDV Direct",
        "app_id":        "vn.com.bidv.direct",
        "customer_type": "Doanh nghiệp",
    },
    {
        "bank_name":     "Techcombank",
        "app_name":      "Techcombank Business",
        "app_id":        "vn.com.techcombank.bb.corp.app",
        "customer_type": "Doanh nghiệp",
    },
    {
        "bank_name":     "MB Bank",
        "app_name":      "BIZ MBBank 2.0",
        "app_id":        "com.mbbank.biz.prod",
        "customer_type": "Doanh nghiệp",
    },
    {
        "bank_name":     "VietinBank",
        "app_name":      "VietinBank eFAST One",
        "app_id":        "com.vietinbank.dbs.efast",
        "customer_type": "Doanh nghiệp",
    },
]

# ==============================================================================
# 2. CẤU HÌNH
# ==============================================================================

SOURCE_GP      = "Google Play"
LANG           = "vi"
COUNTRY        = "vn"
BATCH_SIZE     = 1000
TARGET_PER_APP = 2_000_000   # giới hạn tối đa mỗi app (thực tế bị giới hạn bởi API)

VN_TZ = timezone(timedelta(hours=7))

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "raw_reviews.csv"


# ==============================================================================
# 3. HÀM TIỆN ÍCH
# ==============================================================================

def normalize_time(review_time) -> str:
    """Chuyển đổi thời gian về múi giờ Việt Nam (UTC+7)."""
    if isinstance(review_time, str) and review_time:
        try:
            dt = datetime.fromisoformat(review_time)
            return dt.astimezone(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return review_time
    elif isinstance(review_time, datetime):
        try:
            if review_time.tzinfo is None:
                return review_time.strftime("%Y-%m-%d %H:%M:%S")
            return review_time.astimezone(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(review_time)
    return str(review_time) if review_time else ""


def review_to_row(review: dict, bank_name: str, app_name: str,
                  app_id: str, customer_type: str) -> dict:
    """Chuyển 1 review thô thành dict chuẩn."""
    return {
        "Tên ngân hàng":    bank_name,
        "Tên app":          app_name,
        "Phân khúc KH":     customer_type,
        "Nguồn review":     SOURCE_GP,
        "App ID":           app_id,
        "Review ID":        review.get("reviewId"),
        "Username":         review.get("userName"),
        "Nội dung review":  review.get("content"),
        "Rating":           review.get("score"),
        "Thời gian review": normalize_time(review.get("at")),
        "Version app":      review.get("reviewCreatedVersion"),
        "Số lượt hữu ích":  review.get("thumbsUpCount"),
    }


# ==============================================================================
# 4. CÀO DỮ LIỆU GOOGLE PLAY
# ==============================================================================

def scrape_app(app_info: dict, all_rows: list) -> int:
    """Cào review của 1 app. Trả về số review đã cào được."""
    bank_name     = app_info["bank_name"]
    app_name      = app_info["app_name"]
    app_id        = app_info["app_id"]
    customer_type = app_info["customer_type"]

    print(f"\n{'='*60}")
    print(f"  App   : {app_name}")
    print(f"  Ngân hàng: {bank_name} | Phân khúc: {customer_type}")
    print(f"  App ID: {app_id}")
    print(f"{'='*60}")

    app_reviews: list = []
    continuation_token = None

    while len(app_reviews) < TARGET_PER_APP:
        try:
            result, continuation_token = reviews(
                app_id,
                lang=LANG,
                country=COUNTRY,
                sort=Sort.NEWEST,
                count=BATCH_SIZE,
                continuation_token=continuation_token,
            )

            if not result:
                print(f"  ✓ Không còn review để lấy tiếp.")
                break

            for r in result:
                row = review_to_row(r, bank_name, app_name, app_id, customer_type)
                all_rows.append(row)
                app_reviews.append(row)

            print(f"  Đã lấy: {len(app_reviews):,} | Tổng: {len(all_rows):,}")

            if continuation_token is None:
                print(f"  ✓ Hết continuation_token.")
                break

            time.sleep(2)

        except Exception as e:
            print(f"  ✗ Lỗi: {e}")
            time.sleep(10)
            break

    print(f"  → Tổng review app này: {len(app_reviews):,}")
    return len(app_reviews)


def main():
    print("=" * 60)
    print("  SCRAPER — Cào Review Google Play")
    print(f"  Output: {OUTPUT_PATH}")
    print("=" * 60)

    all_rows: list = []

    for app_info in BANK_APPS:
        scrape_app(app_info, all_rows)

    # ── Tạo DataFrame & loại trùng ────────────────────────────────────────────
    df = pd.DataFrame(all_rows)
    print(f"\n{'='*60}")
    print(f"  Tổng dòng trước khi loại trùng: {len(df):,}")

    if len(df) > 0:
        df = df.drop_duplicates(subset=["Tên app", "Review ID"])
        print(f"  Tổng dòng sau khi loại trùng : {len(df):,}")
        df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"\n Đã lưu {len(df):,} reviews → '{OUTPUT_PATH}'")
    else:
        print("   Không có dữ liệu nào để lưu.")

    print("=" * 60)
    print("\nBước tiếp theo: python process.py")


if __name__ == "__main__":
    main()
