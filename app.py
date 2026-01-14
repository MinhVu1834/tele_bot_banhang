import os
import sqlite3
import threading
import time
from datetime import datetime

import telebot
from telebot import types
from flask import Flask, request

# =========================
# ENV CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@min_max1834").strip()  # @username
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # optional (khuyên set để /setimg chỉ admin)

BANK_NAME = os.getenv("BANK_NAME", "VCB").strip()
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME", "A HI HI").strip()
ACCOUNT_NO = os.getenv("ACCOUNT_NO", "0311000742866").strip()

PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "data.db")

SHOP_NAME = os.getenv("SHOP_NAME", "SHOP X").strip()

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN env var")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
server = Flask(__name__)

# =========================
# DB (SQLite) - store image file_id by key
# =========================
def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def set_image(key: str, file_id: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO images(key, file_id, updated_at)
        VALUES(?,?,?)
        ON CONFLICT(key) DO UPDATE SET file_id=excluded.file_id, updated_at=excluded.updated_at
        """,
        (key.upper(), file_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

def get_image(key: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT file_id FROM images WHERE key=? LIMIT 1", (key.upper(),))
    row = cur.fetchone()
    conn.close()
    return row["file_id"] if row else None

# =========================
# Helpers
# =========================
def admin_url() -> str:
    u = ADMIN_USERNAME.lstrip("@")
    return f"https://t.me/{u}"

def is_admin(user) -> bool:
    if ADMIN_CHAT_ID and user.id == ADMIN_CHAT_ID:
        return True
    admin_u = ADMIN_USERNAME.lstrip("@").lower()
    u = (user.username or "").lower()
    return u == admin_u

def send_with_optional_photo(chat_id: int, img_key: str, caption: str, reply_markup=None):
    file_id = get_image(img_key)
    if file_id:
        bot.send_photo(chat_id, file_id, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=reply_markup)

def safe_send_markdown(chat_id: int, text: str, reply_markup=None):
    # message limit ~4096; keep a safe margin
    if len(text) <= 3500:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)
        return
    parts = text.split("\n\n")
    buf = ""
    for p in parts:
        if len(buf) + len(p) + 2 > 3500:
            bot.send_message(chat_id, buf, parse_mode="Markdown")
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf:
        bot.send_message(chat_id, buf, parse_mode="Markdown", reply_markup=reply_markup)

# =========================
# CATALOG (ORDER AS REQUESTED)
# TELE, FB, WEB, DOMAIN, MB, OTP
# =========================
CATALOG = [
    # 1) TELE
    {
        "cat_id": "TELE",
        "title": "📱 TELE",
        "desc": (
            "⭐ **DANH MỤC TELE**\n"
            "✅ Giá rõ ràng – hỗ trợ nhanh – bàn giao gọn\n"
            "👉 Chọn sản phẩm bên dưới 👇"
        ),
        "items": [
            {
                "item_id": "TELE_BASIC",
                "name": "Tài khoản Telegram cơ bản",
                "price": "25.000đ",
                "detail": (
                    "🐙 **Tài khoản Telegram cơ bản**\n"
                    "💰 Giá: **25.000đ**\n"
                    "📌 Hỗ trợ đăng nhập ban đầu"
                ),
                "buy_template": "MUA TELE CƠ BẢN | SL: 1 | Telegram: {u}"
            },
            {
                "item_id": "TELE_ADV",
                "name": "Tài khoản có tiện ích nâng cao",
                "price": "200.000đ",
                "detail": (
                    "🐙 **Tài khoản Telegram có sẵn tiện ích nâng cao**\n"
                    "💰 Giá: **200.000đ**\n"
                    "📌 Phù hợp nhu cầu sử dụng nâng cao"
                ),
                "buy_template": "MUA TELE NÂNG CAO | SL: 1 | Telegram: {u}"
            },
            {
                "item_id": "TELE_PHONE_PACK",
                "name": "Gói số điện thoại đăng ký tài khoản",
                "price": "80.000đ",
                "detail": (
                    "🐙 **Gói số điện thoại phục vụ đăng ký tài khoản**\n"
                    "💰 Giá: **80.000đ / gói**\n"
                    "📌 Hỗ trợ trong vòng **24h** nếu chưa sử dụng mà gặp sự cố (theo điều kiện)\n\n"
                    "🎁 Mua từ **20** tặng:\n"
                    "✅ 1 tiện ích nâng cao\n"
                    "✅ hoặc 1 nhóm mẫu (~1.700 thành viên)\n\n"
                    "📌 Khuyến nghị tăng cường bảo mật sau khi nhận"
                ),
                "buy_template": "MUA GÓI SỐ ĐK TELE | SL: 1 | Telegram: {u} | Nhu cầu: ..."
            },
        ],
        "warranty": (
            "⚠️ **LƯU Ý**\n"
            "- Chủ động tăng cường bảo mật sau khi nhận\n"
            "- Không áp dụng hỗ trợ nếu tài khoản bị hạn chế do vi phạm quy định"
        )
    },

    # 2) FB
    {
        "cat_id": "FB",
        "title": "📘 FB",
        "desc": (
            "⭐ **DANH MỤC FACEBOOK**\n"
            "✅ Giá rõ ràng – hỗ trợ nhanh – bàn giao gọn\n"
            "👉 Chọn sản phẩm bên dưới 👇"
        ),
        "items": [
            {
                "item_id": "FB_ACTIVE",
                "name": "Tài khoản hoạt động cao",
                "price": "150.000đ",
                "detail": (
                    "🟢 **Tài khoản hoạt động cao – phù hợp đăng bài & quản lý nội dung**\n"
                    "💰 Giá: **150.000đ**\n"
                    "📌 Phù hợp cho nhu cầu chia sẻ nội dung thường xuyên\n"
                    "📌 Không áp dụng bảo hành dài hạn"
                ),
                "buy_template": "MUA FB HOẠT ĐỘNG CAO | SL: 1 | Telegram: {u}"
            },
            {
                "item_id": "FB_PAGE_MANAGER",
                "name": "Tài khoản quản lý Page",
                "price": "250.000đ",
                "detail": (
                    "🟢 **Tài khoản quản lý Page**\n"
                    "💰 Giá: **250.000đ**\n"
                    "📌 Đã xác minh danh tính (theo điều kiện)\n"
                    "📌 Khuyến nghị giữ nguyên thông tin ban đầu để đảm bảo ổn định\n"
                    "📌 Hỗ trợ trong **24 giờ** (theo điều kiện)"
                ),
                "buy_template": "MUA FB QUẢN LÝ PAGE | SL: 1 | Telegram: {u}"
            },
            {
                "item_id": "FB_OLD",
                "name": "Tài khoản lâu năm 2019–2024",
                "price": "450.000đ–1.500.000đ",
                "detail": (
                    "🟢 **Tài khoản lâu năm (2019 – 2024)**\n"
                    "💰 Giá: **450.000đ – 1.500.000đ**\n"
                    "📌 Có lịch sử hoạt động & bài đăng\n"
                    "📌 Phù hợp xây dựng hình ảnh cá nhân / thương hiệu\n"
                    "📌 Có ID để khách kiểm tra & lựa chọn"
                ),
                "buy_template": "MUA FB LÂU NĂM | Nhu cầu: ... | Telegram: {u}"
            },
            {
                "item_id": "FB_VERIFY",
                "name": "Tài khoản xác minh nâng cao",
                "price": "500.000đ (duy trì 200k/tháng)",
                "detail": (
                    "🟢 **Tài khoản xác minh nâng cao**\n"
                    "💰 Giá: **500.000đ**\n"
                    "📌 Phí duy trì hàng tháng: **200.000đ**"
                ),
                "buy_template": "MUA FB XÁC MINH NÂNG CAO | SL: 1 | Telegram: {u}"
            },
        ],
        "warranty": (
            "⚠️ **CHÍNH SÁCH HỖ TRỢ**\n"
            "- Hỗ trợ đăng nhập ban đầu\n"
            "- Hỗ trợ trạng thái hoạt động trong **24h** (tuỳ gói/điều kiện)\n"
            "- Trường hợp vi phạm chính sách nền tảng sẽ **không áp dụng hỗ trợ**\n"
            "- Khuyến nghị đổi mật khẩu, email và thông tin bảo mật sau khi nhận"
        )
    },

    # 3) LÀM WEB
    {
        "cat_id": "WEB",
        "title": "🖥️ LÀM WEB",
        "desc": (
            "🖥️ **LÀM WEBSITE**\n"
            "💬 **Giá:** Thương lượng theo nhu cầu\n\n"
            "✅ Landing page / website bán hàng / giới thiệu\n"
            "✅ Có hosting + domain (nếu cần)\n"
            "✅ Tối ưu tốc độ – giao diện đẹp\n\n"
            "👉 Nhấn **NHẮN ADMIN** để báo yêu cầu, admin tư vấn & báo giá 👇"
        ),
        "items": [
            {
                "item_id": "WEB_QUOTE",
                "name": "Tư vấn & báo giá website",
                "price": "Thương lượng",
                "detail": (
                    "🖥️ **TƯ VẤN & BÁO GIÁ WEBSITE**\n"
                    "💬 Giá: **Thương lượng**\n\n"
                    "📌 Bạn gửi admin nhu cầu: loại web, chức năng, mẫu tham khảo, thời gian hoàn thành."
                ),
                "buy_template": "TƯ VẤN WEBSITE | Loại web: ... | Mục tiêu: ... | Tham khảo: ... | Telegram: {u}"
            },
        ],
        "warranty": ""
    },

    # 4) TÊN MIỀN
    {
        "cat_id": "DOMAIN",
        "title": "🌐 TÊN MIỀN",
        "desc": (
            "🌐 **TÊN MIỀN – ĐỒNG GIÁ 370.000đ / 1 DOMAIN**\n\n"
            "✅ **Bảo hành suốt thời gian sử dụng**\n"
            "✅ **Đổi hậu đài ~ 3 phút**\n"
            "📌 Hỗ trợ chọn đuôi/keyword theo nhu cầu\n\n"
            "👉 Chọn mục bên dưới để mua 👇"
        ),
        "items": [
            {
                "item_id": "DOMAIN_370",
                "name": "Tên miền đồng giá",
                "price": "370.000đ",
                "detail": (
                    "🌐 **TÊN MIỀN – 370.000đ / 1 DOMAIN**\n\n"
                    "✅ Bảo hành suốt thời gian sử dụng\n"
                    "✅ Đổi hậu đài ~ 3 phút\n\n"
                    "📌 Khi nhắn admin, bạn ghi rõ: đuôi mong muốn (.com/.net/...) + keyword."
                ),
                "buy_template": "MUA TÊN MIỀN | Đuôi: .com/.net/... | Keyword: ... | Telegram: {u}"
            },
        ],
        "warranty": ""
    },

    # 5) STK MB BANK
    {
        "cat_id": "MB",
        "title": "🏦 STK MB BANK",
        "desc": (
            "🏦 **TK MB BANK – 13.000đ / 1 TK**\n"
            "🎮 Phù hợp nhu cầu tạo tài khoản game\n"
            "⚡ Giao nhanh sau khi xác nhận thanh toán\n\n"
            "👉 Chọn mục bên dưới để mua 👇"
        ),
        "items": [
            {
                "item_id": "MB_13K",
                "name": "TK MB Bank",
                "price": "13.000đ",
                "detail": (
                    "🏦 **TK MB BANK**\n"
                    "💰 Giá: **13.000đ / 1 TK**\n"
                    "🎮 Chuyên dùng tạo tài khoản game\n"
                    "⚡ Giao nhanh sau khi xác nhận thanh toán"
                ),
                "buy_template": "MUA TK MB BANK | SL: 1 | Telegram: {u}"
            },
        ],
        "warranty": ""
    },

    # 6) OTP SDT
    {
        "cat_id": "OTP",
        "title": "📲 OTP SDT",
        "desc": (
            "📲 **SĐT ĐĂNG KÝ GAME (OTP)**\n"
            "💰 **7.000đ / 1 OTP**\n"
            "⚡ Hỗ trợ nhanh – thao tác đơn giản\n\n"
            "👉 Chọn mục bên dưới để mua 👇"
        ),
        "items": [
            {
                "item_id": "OTP_7K",
                "name": "OTP SĐT đăng ký game",
                "price": "7.000đ",
                "detail": (
                    "📲 **OTP SĐT ĐĂNG KÝ GAME**\n"
                    "💰 Giá: **7.000đ / 1 OTP**\n\n"
                    "📌 Khi nhắn admin, bạn ghi rõ nền tảng/game cần OTP."
                ),
                "buy_template": "MUA OTP GAME | SL: 1 | Nền tảng/game: ... | Telegram: {u}"
            },
        ],
        "warranty": ""
    },
]

CAT_BY_ID = {c["cat_id"]: c for c in CATALOG}
ITEM_BY_ID = {}
for c in CATALOG:
    for it in c.get("items", []):
        ITEM_BY_ID[it["item_id"]] = (c["cat_id"], it)

# =========================
# UI Builders
# =========================
def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=1)
    # order already as user requested
    for c in CATALOG:
        kb.add(types.InlineKeyboardButton(c["title"], callback_data=f"CAT|{c['cat_id']}"))
    kb.add(types.InlineKeyboardButton("💳 THÔNG TIN THANH TOÁN", callback_data="PAY"))
    kb.add(types.InlineKeyboardButton("📩 LIÊN HỆ ADMIN", url=admin_url()))
    return kb

def kb_back_main():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("⏪ Quay lại Menu", callback_data="BACK_MAIN"))
    return kb

def kb_category(cat_id: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    cat = CAT_BY_ID.get(cat_id)
    if not cat:
        kb.add(types.InlineKeyboardButton("⏪ Quay lại Menu", callback_data="BACK_MAIN"))
        return kb

    # list items inside category
    for it in cat.get("items", []):
        label = f"{it['name']} | {it['price']}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"ITEM|{it['item_id']}"))

    kb.add(types.InlineKeyboardButton("💳 THÔNG TIN THANH TOÁN", callback_data="PAY"))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại Menu", callback_data="BACK_MAIN"))
    return kb

def kb_item(item_id: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✅ MUA NGAY", callback_data=f"BUY|{item_id}"))
    kb.add(types.InlineKeyboardButton("💳 THÔNG TIN THANH TOÁN", callback_data="PAY"))
    kb.add(types.InlineKeyboardButton("📩 NHẮN ADMIN", url=admin_url()))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại Danh mục", callback_data=f"BACKCAT|{item_id}"))
    return kb

def kb_buy(item_id: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📩 NHẮN ADMIN NGAY", url=admin_url()))
    kb.add(types.InlineKeyboardButton("💳 THÔNG TIN THANH TOÁN", callback_data="PAY"))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại Menu", callback_data="BACK_MAIN"))
    return kb

def kb_payment():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📩 GỬI BILL CHO ADMIN", url=admin_url()))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại Menu", callback_data="BACK_MAIN"))
    return kb

# =========================
# Text blocks
# =========================
def text_start():
    return (
        f"👋 **Chào mừng bạn đến với {SHOP_NAME}**\n\n"
        "✅ Giá rõ ràng – hỗ trợ nhanh – bàn giao gọn\n"
        "⚡ Chọn danh mục → chọn sản phẩm → nhắn admin theo mẫu\n\n"
        "👉 Chọn danh mục bạn cần bên dưới 👇"
    )

def text_payment():
    return (
        f"💳 **THÔNG TIN THANH TOÁN – {SHOP_NAME}**\n\n"
        f"🏦 **Ngân hàng:** Vietcombank ({BANK_NAME})\n"
        f"👤 **Chủ TK:** {ACCOUNT_NAME}\n"
        f"🔢 **STK:** {ACCOUNT_NO}\n\n"
        "✅ **NỘI DUNG CHUYỂN KHOẢN (BẮT BUỘC):**\n"
        "`@username + TÊN SẢN PHẨM`\n"
        "Ví dụ: `@abc MB BANK` / `@abc TÊN MIỀN` / `@abc OTP` / `@abc TELE CƠ BẢN`\n\n"
        "📌 Chuyển xong, chụp bill gửi admin để xác nhận nhanh."
    )

def category_message(cat_id: str):
    cat = CAT_BY_ID.get(cat_id)
    if not cat:
        return "❌ Danh mục không tồn tại."
    base = f"**{cat['title']}**\n\n{cat.get('desc','')}".strip()
    if cat.get("warranty"):
        base += "\n\n" + cat["warranty"]
    return base

def item_message(item_id: str):
    found = ITEM_BY_ID.get(item_id)
    if not found:
        return "❌ Sản phẩm không tồn tại."
    _, it = found
    return f"✅ **{it['name']}**\n💰 Giá: **{it['price']}**\n\n{it['detail']}"

def buy_message(item_id: str, username: str):
    found = ITEM_BY_ID.get(item_id)
    if not found:
        return "❌ Sản phẩm không tồn tại."
    _, it = found
    u = f"@{username}" if username else "@username"
    template = it["buy_template"].format(u=u)
    return (
        "✅ Để mua hàng, bạn vui lòng **copy mẫu** và gửi admin 👇\n\n"
        "**📋 MẪU NHẮN ADMIN (COPY):**\n"
        f"`{template}`\n\n"
        "📌 Admin sẽ xác nhận và bàn giao sau khi thanh toán."
    )

def img_key_for_category(cat_id: str) -> str:
    return f"CAT_{cat_id}"

def img_key_for_item(item_id: str) -> str:
    return f"ITEM_{item_id}"

# =========================
# Commands
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    send_with_optional_photo(message.chat.id, "START", text_start(), reply_markup=kb_main())

@bot.message_handler(commands=["getid"])
def cmd_getid(message):
    bot.send_message(
        message.chat.id,
        "📌 **/getid**: Gửi **1 ảnh** vào đây, bot sẽ trả về `file_id`.\n\n"
        "Nếu bạn là admin muốn gắn ảnh cho từng màn:\n"
        "- `/setimg START` (banner)\n"
        "- `/setimg PAYMENT` (màn thanh toán)\n"
        "- `/setimg CAT_<DANH_MỤC>` (ví dụ: `CAT_TELE`)\n"
        "- `/setimg ITEM_<ID>` (ví dụ: `ITEM_MB_13K`)\n\n"
        "Xem danh sách KEY đầy đủ bằng lệnh: `/listkeys`",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["listkeys"])
def cmd_listkeys(message):
    keys = ["START", "PAYMENT"]
    for c in CATALOG:
        keys.append(img_key_for_category(c["cat_id"]))
        for it in c.get("items", []):
            keys.append(img_key_for_item(it["item_id"]))
    text = "🗂️ **Danh sách KEY ảnh có thể gắn:**\n\n" + "\n".join([f"- `{k}`" for k in keys])
    safe_send_markdown(message.chat.id, text)

admin_waiting_img_key = {}  # chat_id -> key

@bot.message_handler(commands=["setimg"])
def cmd_setimg(message):
    if not is_admin(message.from_user):
        bot.reply_to(message, "⛔ Lệnh này chỉ dành cho admin.")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "✅ Dùng: `/setimg KEY`\nXem KEY: `/listkeys`", parse_mode="Markdown")
        return

    key = parts[1].strip().upper()
    admin_waiting_img_key[message.chat.id] = key
    bot.reply_to(message, f"📷 OK. Giờ hãy gửi **ảnh** để gắn vào KEY: **{key}**.", parse_mode="Markdown")

@bot.message_handler(content_types=["photo"])
def on_photo(message):
    file_id = message.photo[-1].file_id

    # luôn trả file_id cho người gửi
    bot.reply_to(message, f"✅ file_id:\n`{file_id}`", parse_mode="Markdown")

    # nếu admin đang setimg
    key = admin_waiting_img_key.get(message.chat.id)
    if key and is_admin(message.from_user):
        set_image(key, file_id)
        admin_waiting_img_key.pop(message.chat.id, None)
        bot.reply_to(message, f"✅ Đã gắn ảnh cho **{key}**.", parse_mode="Markdown")

# =========================
# Callbacks
# =========================
@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        data = call.data
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id)

        if data == "BACK_MAIN":
            send_with_optional_photo(chat_id, "START", text_start(), reply_markup=kb_main())
            return

        if data == "PAY":
            send_with_optional_photo(chat_id, "PAYMENT", text_payment(), reply_markup=kb_payment())
            return

        if data.startswith("CAT|"):
            cat_id = data.split("|", 1)[1]
            text = category_message(cat_id)
            img_key = img_key_for_category(cat_id)
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_category(cat_id))

            # bonus: nếu là WEB thì gửi thêm mẫu nhắn admin
            if cat_id == "WEB":
                u = f"@{call.from_user.username}" if call.from_user.username else "@username"
                safe_send_markdown(
                    chat_id,
                    "**📋 MẪU NHẮN ADMIN (COPY):**\n"
                    f"`TƯ VẤN WEBSITE | Loại web: ... | Mục tiêu: ... | Tham khảo: ... | Telegram: {u}`"
                )
            return

        if data.startswith("ITEM|"):
            item_id = data.split("|", 1)[1]
            text = item_message(item_id)
            img_key = img_key_for_item(item_id)
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_item(item_id))
            return

        if data.startswith("BACKCAT|"):
            item_id = data.split("|", 1)[1]
            found = ITEM_BY_ID.get(item_id)
            if not found:
                send_with_optional_photo(chat_id, "START", text_start(), reply_markup=kb_main())
                return
            cat_id, _ = found
            text = category_message(cat_id)
            img_key = img_key_for_category(cat_id)
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_category(cat_id))
            return

        if data.startswith("BUY|"):
            item_id = data.split("|", 1)[1]
            username = call.from_user.username or ""
            text = buy_message(item_id, username)
            img_key = img_key_for_item(item_id)  # reuse item image
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_buy(item_id))
            return

        bot.send_message(chat_id, "❓ Không hiểu thao tác. Gõ /start để bắt đầu lại.")

    except Exception as e:
        try:
            bot.send_message(call.message.chat.id, f"⚠️ Có lỗi nhỏ xảy ra. Vui lòng thử lại.\n\nChi tiết: {e}")
        except Exception:
            pass

# =========================
# Flask endpoints for UptimeRobot ping
# =========================
@server.get("/")
def home():
    return "OK", 200

@server.get("/health")
def health():
    return "OK", 200

@server.before_request
def log_ping():
    if request.path in ("/", "/health"):
        print(
            f"[PING] {datetime.utcnow().isoformat()} "
            f"from={request.headers.get('X-Forwarded-For','')} "
            f"ua={request.headers.get('User-Agent','')}"
        )

# =========================
# Run polling in background thread
# =========================
def run_bot_polling_forever():
    while True:
        try:
            print("[BOT] polling started")
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(f"[BOT] polling crashed: {e}. Restart in 5s...")
            time.sleep(5)

def main():
    init_db()
    t = threading.Thread(target=run_bot_polling_forever, daemon=True)
    t.start()

    print(f"[WEB] starting flask on 0.0.0.0:{PORT}")
    server.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
