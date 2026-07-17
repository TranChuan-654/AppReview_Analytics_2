# Sử dụng Python image chính thức bản slim (Debian Bookworm) để giảm dung lượng image
FROM python:3.12-slim-bookworm

# Thiết lập các biến môi trường để Python chạy mượt mà trong Docker
# UV_SYSTEM_PYTHON=1 giúp uv cài đặt trực tiếp vào môi trường Python hệ thống của container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# Cài đặt công cụ quản lý package siêu tốc 'uv' của Astral bằng cách copy binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cài đặt các dependencies hệ thống cần thiết (nếu có)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Sao chép file requirements.txt vào thư mục làm việc
COPY requirements.txt .

# Sử dụng 'uv' thay thế cho 'pip' để cài đặt thư viện nhanh hơn gấp nhiều lần
RUN uv pip install --no-cache -r requirements.txt

# Chạy thử underthesea một lần để tải trước các mô hình tách từ (model) về máy trong quá trình build image,
# tránh việc container tải ở runtime làm chậm hoặc lỗi nếu không có mạng.
RUN python -c "import underthesea; underthesea.word_tokenize('Xin chào Việt Nam')"

# Sao chép toàn bộ mã nguồn của dự án vào container (trừ các file/thư mục được định nghĩa trong .dockerignore)
COPY . .

# Tạo sẵn thư mục lưu trữ dữ liệu
RUN mkdir -p /app/data

# Khai báo VOLUME để có thể đồng bộ (mount) thư mục data ra ngoài máy thật (host)
VOLUME ["/app/data"]

# Mặc định khi chạy container mà không chỉ định command, nó sẽ chạy scraper.py để cào dữ liệu trước.
# Bạn cũng có thể ghi đè command để chạy pipeline xử lý dữ liệu (process.py).
CMD ["python", "scraper.py"]

