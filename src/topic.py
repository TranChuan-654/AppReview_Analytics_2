"""
src/topic.py — Phân loại sản phẩm & vấn đề lỗi (3 tầng)
==========================================================
Tầng 1 (Sản phẩm)  : keyword phân cấp → Sản phẩm 1/2/3
Tầng 2 (Vấn đề lỗi): Rule-based keyword + product inference → Vấn đề lỗi 1/2/3
Tầng 3 (Vấn đề lỗi): TF-IDF + LogisticRegression re-label nhóm "Lỗi chung"
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd


# ══════════════════════════════════════════════════════════════════════════
# SHARED UTILS
# ══════════════════════════════════════════════════════════════════════════

def _remove_accents(s: str) -> str:
    if not isinstance(s, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_s = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_s.replace("đ", "d").replace("Đ", "D").lower()


def _normalize(text: str) -> str:
    t = str(text).lower().strip().replace("_", " ")
    return t + " " + _remove_accents(t)


def _contains_any(norm: str, phrases: list[str]) -> bool:
    return any(p.lower() in norm for p in phrases)


# ══════════════════════════════════════════════════════════════════════════
# PHẦN A — PHÂN LOẠI SẢN PHẨM / TÍNH NĂNG
# ══════════════════════════════════════════════════════════════════════════

_PRODUCT_KEYWORDS: dict[str, dict] = {
    "OTP/Smart OTP": {
        "substrings": ["smart otp", "mã otp", "ma otp", "mã xác thực", "ma xac thuc",
                       "nhận mã", "nhan ma", "gửi mã", "gui ma"],
        "regex": [r"\botp\b"],
    },
    "Đăng nhập/Xác thực": {
        "substrings": ["đăng nhập", "dang nhap", "login", "mật khẩu", "mat khau",
                       "face id", "faceid", "vân tay", "van tay", "sinh trắc", "sinh trac"],
        "regex": [r"\bmk\b", r"\bdn\b", r"\bpass\b"],
    },
    "Thanh toán QR/VietQR": {
        "substrings": ["vietqr", "quét mã", "quet ma", "quét qr", "quet qr",
                       "mã qr", "ma qr", "qr code", "qrcode"],
        "regex": [r"\bqr\b"],
    },
    "Chuyển tiền": {
        "substrings": ["chuyển tiền", "chuyen tien", "chuyển khoản", "chuyen khoan",
                       "giao dịch", "giao dich", "chuyển nhanh", "napas", "gửi tiền", "nhận tiền"],
        "regex": [r"\bck\b", r"\bgd\b"],
    },
    "Thông báo biến động số dư": {
        "substrings": ["biến động số dư", "bien dong so du", "thông báo số dư",
                       "thông báo", "thong bao", "tin nhắn số dư", "sms số dư"],
        "regex": [r"\bsms\b", r"\bott\b", r"\bbdsd\b"],
    },
    "eKYC/Mở tài khoản online": {
        "substrings": ["mở tài khoản", "mo tai khoan", "định danh", "dinh danh",
                       "chụp cccd", "quét cccd", "xác minh danh tính"],
        "regex": [r"\bekyc\b", r"\bkyc\b", r"\bcccd\b", r"\bcmnd\b"],
    },
    "Nạp tiền/Ví điện tử": {
        "substrings": ["nạp tiền", "nap tien", "ví điện tử", "momo", "zalopay",
                       "shopeepay", "vnpay"],
        "regex": [r"\bvi\b"],
    },
    "Thanh toán hóa đơn": {
        "substrings": ["thanh toán", "thanh toan", "hóa đơn", "hoa don",
                       "tiền điện", "tiền nước", "tiền mạng"],
        "regex": [],
    },
    "Rút tiền": {
        "substrings": ["rút tiền", "rut tien", "cây atm", "máy atm"],
        "regex": [r"\batm\b"],
    },
    "Thẻ tín dụng": {
        "substrings": ["thẻ tín dụng", "the tin dung", "thẻ credit", "trả góp qua thẻ"],
        "regex": [r"\bvisa\b", r"\bmastercard\b", r"\bcredit\b"],
    },
    "Thẻ ATM/Ghi nợ": {
        "substrings": ["thẻ atm", "the atm", "thẻ ghi nợ", "thẻ napas", "thẻ vật lý"],
        "regex": [r"\bdebit\b"],
    },
    "Tiết kiệm online": {
        "substrings": ["tiết kiệm", "tiet kiem", "gửi tiết kiệm", "sổ tiết kiệm", "lãi suất"],
        "regex": [],
    },
    "Khoản vay": {
        "substrings": ["khoản vay", "vay tiền", "vay tiêu dùng", "tín chấp", "thấu chi"],
        "regex": [r"\bvay\b"],
    },
    "Phí dịch vụ": {
        "substrings": ["phí dịch vụ", "phi dich vu", "phí chuyển tiền",
                       "phí thường niên", "thu phí", "trừ tiền phí"],
        "regex": [r"\bfee\b", r"\bphi\b"],
    },
    "CSKH/Hỗ trợ": {
        "substrings": ["hỗ trợ", "ho tro", "tổng đài", "tong dai", "hotline",
                       "nhân viên", "cskh", "chăm sóc khách hàng"],
        "regex": [],
    },
    "Bảo mật tài khoản": {
        "substrings": ["bảo mật", "bao mat", "lừa đảo", "lua dao", "hack",
                       "không an toàn", "rò rỉ"],
        "regex": [],
    },
    "Giao diện/UX": {
        "substrings": ["giao diện", "giao dien", "dễ dùng", "de dung", "dễ sử dụng",
                       "khó dùng", "trải nghiệm", "màu sắc", "rườm rà", "bố cục"],
        "regex": [r"\bux\b", r"\bui\b"],
    },
    "Cập nhật phiên bản": {
        "substrings": ["cập nhật", "cap nhat", "update", "phiên bản", "bản mới", "nâng cấp"],
        "regex": [r"\bver\b"],
    },
    "Tài khoản thanh toán": {
        "substrings": ["tài khoản", "tai khoan", "số tài khoản", "sao kê", "lịch sử giao dịch"],
        "regex": [r"\btk\b"],
    },
    "Khuyến mãi/Ưu đãi": {
        "substrings": ["khuyến mãi", "khuyen mai", "ưu đãi", "quà", "hoàn tiền", "quay thưởng"],
        "regex": [r"\bvoucher\b", r"\bcashback\b"],
    },
}

_GENERAL_PRODUCT = {
    "substrings": [
        "tốt", "tot", "tuyệt vời", "tuyet voi", "tuyệt", "tuyet", "đẹp", "dep",
        "mượt", "muot", "nhanh", "tiện", "tien", "tiện lợi", "tien loi",
        "hài lòng", "hai long", "ok", "ổn", "on", "thích", "thich",
        "good", "nice", "great", "perfect", "5 sao", "5*", "yêu", "yeu",
        "tệ", "te", "chán", "chan", "dở", "kém", "kem", "như hạch", "nhu hach",
        "phế", "phe", "tệ hại", "te hai", "bực", "buc", "ức chế", "uc che",
        "rác", "rac", "lỗi", "loi",
    ],
    "regex": [],
}

# Compile regex
_PRODUCT_COMPILED = {
    prod: {
        "substrings": [s.lower() for s in rules["substrings"]],
        "regex": [re.compile(r, re.IGNORECASE) for r in rules["regex"]],
    }
    for prod, rules in _PRODUCT_KEYWORDS.items()
}
_GENERAL_COMPILED = {
    "substrings": [s.lower() for s in _GENERAL_PRODUCT["substrings"]],
    "regex": [],
}


def _tag_products(text: str, sentiment: str) -> list[str]:
    """Phân loại sản phẩm theo thứ tự ưu tiên."""
    if pd.isna(text):
        return ["Khác"]

    t_orig = str(text).lower().replace("_", " ")
    t_no_acc = _remove_accents(t_orig)

    matched = []
    for prod, rules in _PRODUCT_COMPILED.items():
        hit = any(sub in t_orig or sub in t_no_acc for sub in rules["substrings"])
        if not hit:
            hit = any(rx.search(t_orig) or rx.search(t_no_acc) for rx in rules["regex"])
        if hit:
            matched.append(prod)

    if matched:
        return matched

    # Kiểm tra nhận xét chung
    is_general = any(
        sub in t_orig or sub in t_no_acc for sub in _GENERAL_COMPILED["substrings"]
    )
    if is_general:
        s = str(sentiment).strip()
        if s == "Positive":
            return ["Nhận xét khen chung"]
        elif s == "Negative":
            return ["Lỗi chung/Không rõ"]
        return ["Khác"]

    return ["Khác"]


# ══════════════════════════════════════════════════════════════════════════
# PHẦN B — PHÂN LOẠI VẤN ĐỀ LỖI
# ══════════════════════════════════════════════════════════════════════════

_GENERAL_ISSUE = "Lỗi chung/Không xác định"

_NO_PROBLEM_PHRASES = [
    "không lỗi", "không có lỗi", "ko lỗi", "ko có lỗi",
    "không bị lỗi", "không gặp lỗi", "chưa thấy lỗi",
    "không vấn đề", "không có vấn đề", "chưa gặp vấn đề",
    "không sao", "chưa lỗi", "không phát sinh lỗi",
]

_ISSUE_KEYWORDS: dict[str, list[str]] = {
    "Lỗi đăng nhập": [
        "không đăng nhập được", "lỗi đăng nhập", "đăng nhập không được",
        "không vào được app", "mở app không được", "vào app không được",
        "đăng nhập thất bại", "login thất bại", "không login được",
        "bị đăng xuất liên tục", "tự đăng xuất",
        "không_đăng_nhập_được", "lỗi_đăng_nhập", "tự_đăng_xuất",
    ],
    "Lỗi OTP": [
        "không nhận được otp", "không nhận otp", "otp không về",
        "mã không về", "không gửi otp", "không gửi mã",
        "otp lâu", "otp chậm", "chờ otp mãi", "lỗi otp",
        "smart otp lỗi", "mã xác thực không về", "không nhận được mã",
        "đợi otp mãi", "otp không đến",
        "không_nhận_được_otp", "otp_không_về", "lỗi_otp",
    ],
    "Lỗi quét mã QR": [
        "quét mã qr không được", "quét qr không được",
        "qr không quét được", "mã qr lỗi", "không quét được qr",
        "lỗi qr", "scan qr lỗi", "quét qr thất bại",
        "quét mãi không được", "qr code lỗi", "qr bị lỗi",
        "quét_mã_qr_không_được", "mã_qr_lỗi",
    ],
    "Lỗi chuyển tiền/Thanh toán": [
        "chuyển tiền không được", "chuyển tiền bị lỗi",
        "không chuyển được", "chuyển khoản thất bại",
        "giao dịch thất bại", "lỗi giao dịch", "giao dịch lỗi",
        "giao dịch không thành công", "tiền không về",
        "thanh toán không được", "thanh toán thất bại",
        "nạp tiền không được", "rút tiền không được",
        "chuyển_tiền_không_được", "giao_dịch_thất_bại", "tiền_không_về",
    ],
    "Lỗi thông báo/Biến động số dư": [
        "không thông báo", "không có thông báo", "thông báo chậm",
        "không báo số dư", "không báo tiền", "biến động số dư chậm",
        "không nhận được thông báo", "thông báo không về",
        "không hiện thông báo", "sms không về", "tin nhắn không về",
        "không_thông_báo", "thông_báo_chậm", "sms_không_về",
    ],
    "Lỗi ứng dụng/Crash": [
        "bị crash", "crash app", "tự thoát", "văng ra ngoài", "bị văng ra",
        "bị treo", "treo app", "đơ máy", "app bị đơ",
        "không phản hồi", "bị đứng hình", "lỗi ứng dụng",
        "app bị lỗi", "app lỗi liên tục", "sập app",
        "không hoạt động được", "app không mở được",
        "tự_thoát", "treo_app", "lỗi_ứng_dụng", "sập_app",
    ],
    "Ứng dụng chậm/Lag": [
        "quá chậm", "chậm lắm", "chậm như rùa", "bị lag", "giật lag",
        "tải chậm", "load chậm", "loading mãi", "load mãi",
        "xử lý chậm", "phản hồi chậm", "lâu quá",
        "quay vòng mãi", "xoay vòng mãi", "đợi mãi không xong",
        "giật_lag", "tải_chậm", "xử_lý_chậm",
    ],
    "Lỗi cập nhật/Phiên bản mới": [
        "không cập nhật được", "cập nhật thất bại", "lỗi cập nhật",
        "không update được", "cập nhật xong bị lỗi",
        "bản mới bị lỗi", "phiên bản mới lỗi",
        "sau khi cập nhật lỗi", "buộc cập nhật mãi",
        "cập nhật xong không dùng được",
        "không_cập_nhật_được", "bản_mới_bị_lỗi",
    ],
    "UI/UX khó sử dụng": [
        "khó dùng", "khó sử dụng", "khó thao tác", "rườm rà",
        "phức tạp quá", "giao diện xấu", "giao diện khó dùng",
        "bất tiện lắm", "khó hiểu quá", "khó tìm", "tìm không thấy",
        "thiết kế kém", "ux kém", "ui kém",
        "khó_dùng", "giao_diện_xấu", "tìm_không_thấy",
    ],
    "Lỗi eKYC/Mở tài khoản": [
        "ekyc lỗi", "lỗi ekyc", "ekyc không được",
        "không mở được tài khoản", "chụp cccd không được",
        "nhận diện không được", "xác minh thất bại",
        "không xác minh được", "định danh thất bại",
        "không định danh được", "mở tài khoản không được",
        "lỗi_ekyc", "xác_minh_thất_bại",
    ],
    "Lỗi Face ID/Sinh trắc học": [
        "face id không hoạt động", "face id lỗi",
        "vân tay không nhận", "không nhận vân tay",
        "không nhận diện được mặt", "sinh trắc học lỗi",
        "sinh trắc lỗi", "lỗi face id", "lỗi sinh trắc",
        "không đăng nhập bằng vân tay được",
        "face_id_lỗi", "vân_tay_không_nhận",
    ],
    "Lỗi tài khoản/Số dư": [
        "tài khoản bị khóa", "khóa tài khoản", "tài khoản bị đóng",
        "không xem được số dư", "số dư sai", "số dư không cập nhật",
        "sao kê sai", "lịch sử giao dịch sai",
        "tài_khoản_bị_khóa", "số_dư_sai",
    ],
    "Lỗi thẻ ATM/Tín dụng": [
        "thẻ bị khóa", "khóa thẻ", "thẻ không dùng được",
        "thanh toán thẻ không được", "thẻ bị từ chối",
        "rút tiền thẻ không được", "thẻ lỗi",
        "thẻ_bị_khóa", "thanh_toán_thẻ_không_được",
    ],
    "Trừ tiền sai/Mất tiền": [
        "mất tiền", "trừ tiền sai", "trừ nhầm tiền",
        "trừ tiền không rõ", "tiền bị trừ",
        "bị trừ tiền oan", "mất tiền oan",
        "tiền đi mà không đến",
        "mất_tiền", "trừ_tiền_sai", "tiền_bị_trừ",
    ],
    "Phí cao/Bất hợp lý": [
        "phí cao", "phí đắt", "phí quá cao", "phí vô lý",
        "phí không hợp lý", "thu phí vô tội vạ", "phí ẩn",
        "phí_cao", "phí_vô_lý", "phí_ẩn",
    ],
    "CSKH kém/Hỗ trợ chậm": [
        "hỗ trợ kém", "hỗ trợ chậm", "nhân viên thái độ",
        "không được hỗ trợ", "tổng đài không bắt máy",
        "hotline bận", "gọi không ai nghe", "dịch vụ kém",
        "phục vụ tệ", "hỗ trợ không hiệu quả",
        "hỗ_trợ_kém", "dịch_vụ_kém",
    ],
    "Bảo mật/Lừa đảo": [
        "bị hack", "bị lừa đảo", "lừa đảo",
        "tài khoản bị xâm phạm", "mất tài khoản",
        "không an toàn", "bảo mật kém", "thông tin bị lộ",
        "rò rỉ thông tin", "bị chiếm tài khoản",
        "bị_hack", "lừa_đảo", "bảo_mật_kém",
    ],
    _GENERAL_ISSUE: [
        "bị lỗi", "có lỗi", "hay lỗi", "lỗi hoài",
        "không dùng được", "không sử dụng được",
        "gặp vấn đề", "có vấn đề", "báo lỗi",
        "hiển thị lỗi", "lỗi liên tục", "lỗi mãi",
        "bị_lỗi", "không_dùng_được", "lỗi_liên_tục",
    ],
}

# mapping sản phẩm → issue
_PRODUCT_TO_ISSUE: dict[str, str] = {
    "OTP/Smart OTP":               "Lỗi OTP",
    "Đăng nhập/Xác thực":          "Lỗi đăng nhập",
    "Lỗi Face ID/Sinh trắc học":   "Lỗi Face ID/Sinh trắc học",
    "eKYC/Mở tài khoản online":    "Lỗi eKYC/Mở tài khoản",
    "Giao diện/UX":                "UI/UX khó sử dụng",
    "Thanh toán QR/VietQR":        "Lỗi quét mã QR",
    "Cập nhật phiên bản":          "Lỗi cập nhật/Phiên bản mới",
    "Tài khoản thanh toán":        "Lỗi tài khoản/Số dư",
    "Thông báo biến động số dư":   "Lỗi thông báo/Biến động số dư",
    "Chuyển tiền":                 "Lỗi chuyển tiền/Thanh toán",
    "Thanh toán hóa đơn":          "Lỗi chuyển tiền/Thanh toán",
    "Nạp tiền/Ví điện tử":         "Lỗi chuyển tiền/Thanh toán",
    "Rút tiền":                    "Lỗi chuyển tiền/Thanh toán",
    "Thẻ tín dụng":                "Lỗi thẻ ATM/Tín dụng",
    "Thẻ ATM/Ghi nợ":              "Lỗi thẻ ATM/Tín dụng",
    "CSKH/Hỗ trợ":                 "CSKH kém/Hỗ trợ chậm",
    "Phí dịch vụ":                 "Phí cao/Bất hợp lý",
    "Bảo mật tài khoản":           "Bảo mật/Lừa đảo",
    "Tiết kiệm online":            _GENERAL_ISSUE,
    "Khoản vay":                   _GENERAL_ISSUE,
    "Khuyến mãi/Ưu đãi":          _GENERAL_ISSUE,
    "Lỗi chung/Không rõ":          _GENERAL_ISSUE,
    "Nhận xét khen chung":         "Không có lỗi",
    "Khác":                        _GENERAL_ISSUE,
}


def _tier1_issue(text: str, rating=None, sentiment: str = "", p1: str = "") -> list[str]:
    """Tầng 1: Rule-based keyword + product inference."""
    if not text or str(text).strip() == "":
        return ["Không có lỗi", "Không", "Không"]

    norm = _normalize(text)

    if _contains_any(norm, _NO_PROBLEM_PHRASES):
        return ["Không có lỗi", "Không", "Không"]

    # Đếm keyword match theo từng issue
    scored = []
    for issue, kws in _ISSUE_KEYWORDS.items():
        matched = [kw for kw in kws if kw.lower() in norm]
        if matched:
            scored.append((issue, len(set(matched))))

    specific = [
        iss for iss, _ in sorted(scored, key=lambda x: x[1], reverse=True)
        if iss != _GENERAL_ISSUE
    ]

    try:
        is_low = int(float(rating)) <= 2 if (
            rating is not None and str(rating).lower() not in ("nan", "")
        ) else False
    except Exception:
        is_low = False

    is_pos = str(sentiment).strip() == "Positive"

    if not is_low and is_pos and not specific and _GENERAL_ISSUE not in [i for i, _ in scored]:
        return ["Không có lỗi", "Không", "Không"]

    if specific:
        pad = specific + ["Không", "Không"]
        return [pad[0], pad[1], pad[2]]

    # Product inference
    if p1 and p1 in _PRODUCT_TO_ISSUE:
        inferred = _PRODUCT_TO_ISSUE[p1]
        if inferred == "Không có lỗi":
            return ["Không có lỗi", "Không", "Không"]
        return [inferred, "Không", "Không"]

    if is_low:
        return [_GENERAL_ISSUE, "Không", "Không"]

    return ["Không có lỗi", "Không", "Không"]


def _tier2_relabel(df: pd.DataFrame, proc_col: str) -> pd.DataFrame:
    """
    Tầng 3: Re-label nhóm 'Lỗi chung' bằng TF-IDF Bigram.
    Nếu không có sklearn thì bỏ qua.
    """
    try:
        import warnings
        warnings.filterwarnings("ignore")
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        return df

    mask_gen = df["Vấn đề lỗi 1"] == _GENERAL_ISSUE
    if mask_gen.sum() < 10:
        return df

    df_train = df[~mask_gen & (df["Vấn đề lỗi 1"] != "Không có lỗi")].copy()
    if len(df_train) < 50:
        return df

    X_train = df_train[proc_col].fillna("").astype(str)
    y_train = df_train["Vấn đề lỗi 1"]

    vc = y_train.value_counts()
    valid_labels = vc[vc >= 5].index
    mask_valid = y_train.isin(valid_labels)
    X_train = X_train[mask_valid]
    y_train = y_train[mask_valid]

    if len(X_train) < 30:
        return df

    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, min_df=2)
    X_vec = vec.fit_transform(X_train)

    clf = LogisticRegression(max_iter=300, C=1.0)
    clf.fit(X_vec, y_train)

    df_gen = df[mask_gen].copy()
    X_gen = vec.transform(df_gen[proc_col].fillna("").astype(str))
    proba = clf.predict_proba(X_gen)
    conf = proba.max(axis=1)
    pred = clf.predict(X_gen)

    CONF_THRESHOLD = 0.55
    relabel_mask = conf >= CONF_THRESHOLD
    df.loc[mask_gen & df.index.isin(df_gen.index[relabel_mask]), "Vấn đề lỗi 1"] = pred[relabel_mask]

    return df


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def run(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nhận DataFrame đã có 'sentiment' → thêm các cột:
      Sản phẩm 1/2/3, product_all
      Vấn đề lỗi 1/2/3, issue_all, domain
    """
    df = df.copy()
    proc_col = "processed_text" if "processed_text" in df.columns else "Nội dung sạch"
    sent_col = "sentiment" if "sentiment" in df.columns else None

    # ── Bước A: Phân loại sản phẩm ───────────────────────────────────────────
    print("[Topic] Phân loại sản phẩm...")
    pl = df.apply(
        lambda r: _tag_products(
            r.get(proc_col, ""),
            r.get(sent_col, "") if sent_col else "",
        ),
        axis=1,
    )
    df["product_all"] = pl.apply(lambda x: ", ".join(x))
    df["Sản phẩm 1"]  = pl.apply(lambda x: x[0] if len(x) >= 1 else "Khác")
    df["Sản phẩm 2"]  = pl.apply(lambda x: x[1] if len(x) >= 2 else "Không")
    df["Sản phẩm 3"]  = pl.apply(lambda x: x[2] if len(x) >= 3 else "Không")
    print(f"[Topic] Sản phẩm xong. Top 5:\n{df['Sản phẩm 1'].value_counts().head(5).to_string()}")

    # ── Bước B: Phân loại vấn đề lỗi (Tầng 1) ──────────────────────────────
    print("[Topic] Phân loại vấn đề lỗi (Tầng 1)...")
    il = df.apply(
        lambda r: _tier1_issue(
            r.get(proc_col, ""),
            r.get("Rating"),
            r.get(sent_col, "") if sent_col else "",
            r.get("Sản phẩm 1", ""),
        ),
        axis=1,
    )
    df["Vấn đề lỗi 1"] = il.apply(lambda x: x[0])
    df["Vấn đề lỗi 2"] = il.apply(lambda x: x[1])
    df["Vấn đề lỗi 3"] = il.apply(lambda x: x[2])

    # ── Bước C: Re-label Tầng 3 (TF-IDF + LogisticRegression) ──────────────
    print("[Topic] Re-label nhóm 'Lỗi chung' (Tầng 3 ML)...")
    df = _tier2_relabel(df, proc_col)

    # ── Cột tổng hợp ─────────────────────────────────────────────────────────
    def _combine_issues(row):
        issues = [row["Vấn đề lỗi 1"], row["Vấn đề lỗi 2"], row["Vấn đề lỗi 3"]]
        issues = [i for i in issues if i and i not in ("Không có lỗi", "Không", _GENERAL_ISSUE)]
        return ", ".join(issues) if issues else row["Vấn đề lỗi 1"]

    df["issue_all"] = df.apply(_combine_issues, axis=1)

    # Domain mapping
    _DOMAIN_MAP = {
        "Lỗi đăng nhập":                  "Ứng dụng & Kỹ thuật",
        "Lỗi OTP":                         "Ứng dụng & Kỹ thuật",
        "Lỗi Face ID/Sinh trắc học":       "Ứng dụng & Kỹ thuật",
        "Lỗi ứng dụng/Crash":              "Ứng dụng & Kỹ thuật",
        "Ứng dụng chậm/Lag":               "Ứng dụng & Kỹ thuật",
        "UI/UX khó sử dụng":               "Ứng dụng & Kỹ thuật",
        "Lỗi cập nhật/Phiên bản mới":      "Ứng dụng & Kỹ thuật",
        "Lỗi chuyển tiền/Thanh toán":      "Giao dịch & Thanh toán",
        "Lỗi quét mã QR":                  "Giao dịch & Thanh toán",
        "Trừ tiền sai/Mất tiền":           "Giao dịch & Thanh toán",
        "Lỗi tài khoản/Số dư":             "Tài khoản & Thẻ",
        "Lỗi thẻ ATM/Tín dụng":            "Tài khoản & Thẻ",
        "Lỗi eKYC/Mở tài khoản":          "Tài khoản & Thẻ",
        "Lỗi thông báo/Biến động số dư":   "Tài khoản & Thẻ",
        "CSKH kém/Hỗ trợ chậm":           "Dịch vụ Khách hàng",
        "Phí cao/Bất hợp lý":              "Phí & Lãi suất",
        "Bảo mật/Lừa đảo":                "Bảo mật",
        "Không có lỗi":                    "Không có lỗi",
        _GENERAL_ISSUE:                    "Lỗi chung",
    }
    df["domain"] = df["Vấn đề lỗi 1"].map(_DOMAIN_MAP).fillna("Khác")

    # ── Bước D: K-Means Clustering Topic Mining từ Step 7 ────────────────────
    print("[Topic] Đang chạy K-Means clustering để phân tích topic_name_suggested...")
    
    STOPWORDS_VN = {
        "này","là","và","của","cho","được","không","có","một","trong","với",
        "để","các","đã","rất","nhưng","thì","mà","như","hay","từ","khi",
        "cũng","sao","bị","vì","nên","quá","còn","lại","vào","phải","đến",
        "hơn","tôi","mình","lên","đi","sẽ","luôn","nào","ơi","mới","rồi",
        "đang","sau","trước","ko","dc","nhé","nha","ạ","ah","ừ","thôi",
        "vậy","thế","gì","cái","đây","đó","kia","vẫn","chưa","ra","về",
        "xuống","cần","muốn","thấy","biết",
        "ngân","hàng","bank","mobile","banking",
        "vietinbank","vietcombank","bidv","agribank","mbbank",
        "vcb","vib","vpbank","tpbank","lắm","rồi","dùng","xài",
    }
    
    TOKEN_PATTERN = (
        r"[a-zA-Zàáảãạăắặẳẵằâấậẩẫầèéẻẽẹêếệểễềìíỉĩịòóỏõọôốộổỗồ"
        r"ơớợởỡờùúủũụưứựửữừỳýỷỹỵđÀÁẢÃẠĂẮẶẲẴẰÂẤẬẨẪẦÈÉẺẼẸÊẾỆỂỄỀ"
        r"ÌÍỈĨỊÒÓỎÕỌÔỐỘỔỖỒƠỚỢỞỠỜÙÚỦŨỤƯỨỰỬỮỪỲÝỶỸỴĐ0-9_]{2,}"
    )
    
    def norm_text(text):
        t = str(text).lower()
        return t + " " + t.replace("_", " ")

    TOPIC_RULES = {
        "OTP chậm/lỗi xác thực":         ["otp","smart otp","mã otp","mã xác thực","nhận otp","gửi mã"],
        "Login lỗi/khó đăng nhập":        ["đăng nhập","login","mật khẩu","không vào","khóa tài khoản"],
        "App lag/chậm/crash":             ["chậm","lag","load","đơ","treo","văng","crash","sập","không phản hồi"],
        "Chuyển tiền/Giao dịch lỗi":      ["chuyển tiền","chuyển khoản","giao dịch","tiền không về","trừ tiền"],
        "QR/VietQR lỗi":                  ["qr","vietqr","quét mã","quét qr","scan qr"],
        "Thông báo/Biến động số dư":      ["thông báo","biến động","số dư","sms","tin nhắn"],
        "eKYC/Sinh trắc học/Face ID":     ["ekyc","cccd","căn cước","định danh","sinh trắc","khuôn mặt","face id","vân tay"],
        "Phí/Mất tiền/Trừ nhầm":         ["phí","trừ tiền","mất tiền","thu phí","phí cao"],
        "CSKH/Tổng đài/Hỗ trợ":          ["tổng đài","hotline","hỗ trợ","nhân viên","cskh"],
        "Giao diện/Trải nghiệm tốt":      ["giao diện","dễ dùng","mượt","đẹp","tiện lợi"],
        "Cập nhật phiên bản lỗi":         ["cập nhật","update","phiên bản","bản mới"],
        "Tài khoản/Thẻ lỗi":             ["tài khoản","thẻ","khóa","số dư sai","sao kê"],
        "Phàn nàn chung (review ngắn)":   ["tệ","kém","chán","lỗi","yếu","rác","dở","thất vọng"],
        "Khen chung (review ngắn)":       ["tốt","ok","ổn","hay","nhanh","tiện","mượt","tuyệt"],
    }

    def suggest_topic(kw_text, neg_rate=0.0, pos_rate=0.0):
        t = kw_text.lower()
        best, best_sc = "Chủ đề khác", 0
        for name, kws in TOPIC_RULES.items():
            if name == "Khen chung (review ngắn)" and neg_rate > 45.0:
                continue
            if name == "Phàn nàn chung (review ngắn)" and pos_rate > 55.0:
                continue
                
            sc = sum(1 for kw in kws if kw in t)
            if sc > best_sc:
                best, best_sc = name, sc

        if best == "Chủ đề khác" or best_sc == 0:
            if neg_rate > 60.0:
                return "Lỗi chung/Phàn nàn khác"
            elif pos_rate > 70.0:
                return "Khen ngợi chung khác"
        return best

    valid_mask = df[proc_col].notna() & (df[proc_col].astype(str).str.strip() != "")
    km_corpus_all  = df.loc[valid_mask, proc_col].astype(str).apply(norm_text).tolist()

    if len(km_corpus_all) > 0:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        from sklearn.decomposition import TruncatedSVD
        from sklearn.preprocessing import normalize

        MAX_TRAIN_SAMPLES = 50000
        if len(km_corpus_all) > MAX_TRAIN_SAMPLES:
            np.random.seed(42)
            sample_indices = np.random.choice(len(km_corpus_all), MAX_TRAIN_SAMPLES, replace=False)
            km_corpus_train = [km_corpus_all[i] for i in sample_indices]
        else:
            km_corpus_train = km_corpus_all

        N_CLUSTERS = min(18, max(8, int(np.sqrt(len(km_corpus_all)/2500)) + 6))
        print(f"   [K-Means] Số Cluster tối ưu (K): {N_CLUSTERS}")

        tfidf_km = TfidfVectorizer(
            max_features=10000, stop_words=list(STOPWORDS_VN),
            ngram_range=(1, 2), min_df=5, max_df=0.85,
            token_pattern=TOKEN_PATTERN, sublinear_tf=True
        )
        X_train = tfidf_km.fit_transform(km_corpus_train)

        n_comp = min(120, X_train.shape[1]-1)
        svd = TruncatedSVD(n_components=n_comp, random_state=42)
        Xsvd_train = normalize(svd.fit_transform(X_train))

        km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=15, max_iter=300)
        km.fit(Xsvd_train)

        X_all = tfidf_km.transform(km_corpus_all)
        Xsvd_all = normalize(svd.transform(X_all))
        labels_all = km.predict(Xsvd_all) + 1

        df["topic_cluster"] = 0
        df.loc[valid_mask, "topic_cluster"] = labels_all

        X_orig_all = normalize(X_all)
        centers = np.zeros((N_CLUSTERS, X_all.shape[1]))
        for c in range(N_CLUSTERS):
            mc = (labels_all == c+1)
            if mc.sum() > 0:
                centers[c] = np.asarray(X_orig_all[mc].mean(axis=0)).flatten()

        fn = tfidf_km.get_feature_names_out()
        name_map = {}
        for c in range(N_CLUSTERS):
            cid = c + 1
            n_mem = int((df["topic_cluster"] == cid).sum())
            if n_mem == 0:
                continue
            sub_c = df[df["topic_cluster"] == cid]
            if sent_col in df.columns:
                neg_r = (sub_c[sent_col] == "Negative").sum() / n_mem * 100
                pos_r = (sub_c[sent_col] == "Positive").sum() / n_mem * 100
            else:
                neg_r, pos_r = 0.0, 0.0
                
            top_kw = [fn[i] for i in centers[c].argsort()[-15:][::-1]]
            kw_text = ", ".join(top_kw)
            name_map[cid] = suggest_topic(kw_text, neg_rate=neg_r, pos_rate=pos_r)

        df["topic_name_suggested"] = df["topic_cluster"].map(name_map).fillna("Không xác định")
    else:
        df["topic_cluster"] = 0
        df["topic_name_suggested"] = "Không xác định"

    print(f"[Topic] Vấn đề lỗi xong. Top 5:\n{df['Vấn đề lỗi 1'].value_counts().head(5).to_string()}")
    return df
