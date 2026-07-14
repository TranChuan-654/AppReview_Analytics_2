# AppReview Analytics 2

Hệ thống phân tích đánh giá ứng dụng ngân hàng Việt Nam từ Google Play.

## 📋 Luồng sử dụng

```
Bước 1 → python scraper.py     # Cào dữ liệu
Bước 2 → python process.py     # Xử lý & phân tích
Bước 3 → Mở dashboard/index.html  # Xem dashboard
```

## 🗂 Cấu trúc dự án

```
AppReview_Analytics_2/
├── scraper.py              # Bước 1: Cào Google Play → data/raw_reviews.csv
├── process.py              # Bước 2: Pipeline xử lý → data/analyzed_reviews.csv
├── src/
│   ├── preprocess.py       # Làm sạch văn bản tiếng Việt
│   ├── sentiment.py        # Phân tích cảm xúc (rule-based + PhoBERT)
│   ├── topic.py            # Phân loại sản phẩm & vấn đề lỗi
│   └── wordcloud_gen.py    # Sinh dữ liệu word cloud
├── data/                   # Thư mục dữ liệu (gitignored)
│   ├── raw_reviews.csv     # Output bước 1
│   ├── analyzed_reviews.csv # Output bước 2
│   └── wordcloud_data.json # Output bước 2
├── dashboard/
│   ├── index.html          # Dashboard phân tích (mở thẳng trình duyệt)
│   ├── style.css
│   └── script.js
├── requirements.txt
└── .gitignore
```

## 🚀 Cài đặt

```bash
pip install -r requirements.txt
```

## 📌 Bước 1 — Cào dữ liệu

```bash
python scraper.py
```

→ Tạo file `data/raw_reviews.csv`

## 📌 Bước 2 — Xử lý dữ liệu

```bash
python process.py
```

→ Tạo file `data/analyzed_reviews.csv` và `data/wordcloud_data.json`

**Dùng PhoBERT (tùy chọn, cần GPU):**
```bash
set SENTIMENT_USE_MODEL=true
python process.py
```

## 📌 Bước 3 — Xem Dashboard

Mở file `dashboard/index.html` trong trình duyệt (Chrome/Edge/Firefox).

Upload 2 file:
- **analyzed_reviews.csv** ← bắt buộc
- **wordcloud_data.json** ← tùy chọn (để xem Word Cloud chính xác)

## 📊 Tính năng Dashboard

| Tab | Nội dung |
|---|---|
| Tổng quan | KPI, bảng so sánh ngân hàng, biểu đồ cảm xúc & rating |
| Xu hướng & Lỗi | Timeline theo tháng, top vấn đề lỗi, top sản phẩm |
| Word Cloud | Từ khóa phổ biến theo màu cảm xúc, phân bổ sản phẩm |
| Ý kiến | Danh sách review với phân trang và bộ lọc |

