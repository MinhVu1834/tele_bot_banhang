import os
import sqlite3
import threading
import time
from datetime import datetime
from urllib.parse import quote

import telebot
from telebot import types
from flask import Flask, request

# =========================
# ENV CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@min_max1834").strip()  # @username
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # optional - recommended
SHOP_NAME = os.getenv("SHOP_NAME", "SHOP X").strip()

BANK_NAME = os.getenv("BANK_NAME", "VCB").strip()
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME", "A HI HI").strip()
ACCOUNT_NO = os.getenv("ACCOUNT_NO", "0311000742866").strip()

PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "data.db")

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
def admin_username_clean() -> str:
    return ADMIN_USERNAME.lstrip("@")

def admin_url() -> str:
    return f"https://t.me/{admin_username_clean()}"

def is_admin(user) -> bool:
    if ADMIN_CHAT_ID and user.id == ADMIN_CHAT_ID:
        return True
    admin_u = admin_username_clean().lower()
    u = (user.username or "").lower()
    return u == admin_u

def send_with_optional_photo(chat_id: int, img_key: str, caption: str, reply_markup=None):
    file_id = get_image(img_key)
    if file_id:
        bot.send_photo(chat_id, file_id, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=reply_markup)

def safe_send_markdown(chat_id: int, text: str, reply_markup=None):
    # message limit ~4096; keep margin
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

def build_prefilled_admin_link(text: str) -> str:
    # Opens admin chat with prefilled message
    return f"https://t.me/{admin_username_clean()}?text={quote(text)}"

def user_tag(from_user) -> str:
    return f"@{from_user.username}" if from_user.username else "@username"

# =========================
# Catalog (menu 6 mục, bên trong có sản phẩm nhỏ)
# =========================
# Lưu ý: Đây là khung catalog “marketing”, bạn chỉnh text/giá thoải mái.
CATALOG = [
    # 1) TELE
    {
        "cat_id": "TELE",
        "title": "📱 TELE",
        "desc": "📱 **TELE – Danh mục sản phẩm**\n👉 Chọn mục bên dưới 👇",
        "items": [
            {
                "item_id": "TELE_CLONE",
                "group": "TELE",
                "name": "Tài khoản Telegram cơ bản",
                "price": "25.000đ",
                "detail": "🐙 **Tài khoản Telegram cơ bản**\n💰 Giá: **25.000đ**\n📌 Hỗ trợ đăng nhập ban đầu (theo điều kiện)",
                "require_hint": "Yêu cầu: SL/ghi chú (nếu có)"
            },
            {
                "item_id": "TELE_VIP",
                "group": "TELE",
                "name": "Tài khoản Telegram tiện ích nâng cao",
                "price": "200.000đ",
                "detail": "🐙 **Tài khoản Telegram tiện ích nâng cao**\n💰 Giá: **200.000đ**\n📌 Phù hợp nhu cầu sử dụng nâng cao",
                "require_hint": "Yêu cầu: SL/ghi chú (nếu có)"
            },
            {
                "item_id": "TELE_PACK",
                "group": "TELE",
                "name": "Gói số điện thoại đăng ký (gói 50)",
                "price": "80.000đ",
                "detail": "🐙 **Gói số điện thoại đăng ký**\n💰 Giá: **80.000đ**\n📌 Hỗ trợ theo điều kiện gói\n🎁 Mua số lượng có ưu đãi (tuỳ thời điểm)",
                "require_hint": "Yêu cầu: SL | Mục đích sử dụng"
            },
            {
                "item_id": "TELE_UPSTAR",
                "group": "TELE",
                "name": "Nâng cấp Telegram (bảng gói)",
                "price": "Xem chi tiết",
                "detail": (
                    "🤩 **NÂNG CẤP TELEGRAM**\n\n"
                    "✅ 1 tháng: **125.000đ**\n"
                    "✅ 3 tháng: **380.000đ**\n"
                    "✅ 6 tháng: **550.000đ**\n"
                    "✅ 1 năm: **850.000đ**\n\n"
                    "📌 Hỗ trợ theo thời hạn gói"
                ),
                "require_hint": "Yêu cầu: gói (1m/3m/6m/1y)"
            },
            {
                "item_id": "TELE_GROUP",
                "group": "TELE",
                "name": "Nhóm/Kênh Telegram (bảng size)",
                "price": "Xem chi tiết",
                "detail": (
                    "👥 **NHÓM/KÊNH TELEGRAM**\n\n"
                    "📱 1K7–2K mem: **150.000đ**\n"
                    "📱 5K mem: **400.000đ**\n"
                    "📱 10K mem: **800.000đ**\n"
                    "📱 20K mem: **1.500.000đ**\n\n"
                    "🎁 Mua 8 tặng 1 (cùng loại)\n"
                    "📌 Bàn giao quyền sở hữu theo quy trình"
                ),
                "require_hint": "Yêu cầu: size nhóm/kênh"
            },
        ],
        "img_key": "CAT_TELE",
    },

    # 2) FACEBOOK
    {
        "cat_id": "FB",
        "title": "📘 FACEBOOK",
        "desc": "📘 **FACEBOOK – Danh mục sản phẩm**\n👉 Chọn mục bên dưới 👇",
        "items": [
            {
                "item_id": "FB_ACTIVE",
                "group": "FACEBOOK",
                "name": "Tài khoản hoạt động cao",
                "price": "150.000đ",
                "detail": "🟢 **Tài khoản hoạt động cao**\n💰 Giá: **150.000đ**\n📌 Phù hợp nhu cầu đăng bài / quản lý nội dung",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "FB_PAGE_MANAGER",
                "group": "FACEBOOK",
                "name": "Tài khoản quản lý Page",
                "price": "250.000đ",
                "detail": "🟢 **Tài khoản quản lý Page**\n💰 Giá: **250.000đ**\n📌 Hỗ trợ theo điều kiện gói",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "FB_OLD",
                "group": "FACEBOOK",
                "name": "Tài khoản lâu năm 2019–2024",
                "price": "450.000đ – 1.500.000đ",
                "detail": "🟢 **Tài khoản lâu năm (2019–2024)**\n💰 Giá: **450.000đ – 1.500.000đ**\n📌 Có lựa chọn theo nhu cầu",
                "require_hint": "Yêu cầu: năm/tiêu chí lựa chọn"
            },
            {
                "item_id": "FB_VERIFY",
                "group": "FACEBOOK",
                "name": "Tài khoản xác minh nâng cao",
                "price": "500.000đ (duy trì 200k/tháng)",
                "detail": "🟢 **Xác minh nâng cao**\n💰 Giá: **500.000đ**\n📌 Duy trì: **200.000đ/tháng**",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            # PAGE FB (gộp chung trong mục FACEBOOK để khách dễ bấm)
            {
                "item_id": "PAGE_LIVE",
                "group": "FACEBOOK",
                "name": "Page livestream + quảng bá",
                "price": "750.000đ",
                "detail": "📄 **Page livestream + quảng bá**\n💰 Giá: **750.000đ**\n📌 Bàn giao quyền quản trị theo quy trình",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "PAGE_VERIFY",
                "group": "FACEBOOK",
                "name": "Page xác minh nâng cao",
                "price": "1.500.000đ",
                "detail": "📄 **Page xác minh nâng cao**\n💰 Giá: **1.500.000đ**",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "PAGE_BASIC",
                "group": "FACEBOOK",
                "name": "Page cơ bản hoạt động ổn định",
                "price": "150.000đ",
                "detail": "📄 **Page cơ bản**\n💰 Giá: **150.000đ**",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "PAGE_1K",
                "group": "FACEBOOK",
                "name": "Page có theo dõi ~1K",
                "price": "200.000đ",
                "detail": "📄 **Page ~1K theo dõi**\n💰 Giá: **200.000đ**",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "PAGE_5K",
                "group": "FACEBOOK",
                "name": "Page có theo dõi ~5K",
                "price": "450.000đ",
                "detail": "📄 **Page ~5K theo dõi**\n💰 Giá: **450.000đ**",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
            {
                "item_id": "PAGE_10K",
                "group": "FACEBOOK",
                "name": "Page có theo dõi ~10K",
                "price": "750.000đ",
                "detail": "📄 **Page ~10K theo dõi**\n💰 Giá: **750.000đ**",
                "require_hint": "Yêu cầu: SL/ghi chú"
            },
        ],
        "img_key": "CAT_FB",
    },

    # 3) LÀM WEB
    {
        "cat_id": "WEB",
        "title": "🖥️ LÀM WEB",
        "desc": "🖥️ **LÀM WEBSITE**\n💬 **Giá:** thương lượng theo nhu cầu\n👉 Chọn mục bên dưới 👇",
        "items": [
            {
                "item_id": "WEB_QUOTE",
                "group": "LÀM WEB",
                "name": "Tư vấn & báo giá website",
                "price": "Thương lượng",
                "detail": (
                    "🖥️ **TƯ VẤN & BÁO GIÁ WEBSITE**\n\n"
                    "📌 Bạn gửi admin các thông tin:\n"
                    "- Loại web (landing/bán hàng/giới thiệu)\n"
                    "- Chức năng cần có\n"
                    "- Mẫu tham khảo\n"
                    "- Thời gian mong muốn\n"
                ),
                "require_hint": "Yêu cầu: loại web/chức năng/mẫu"
            },
        ],
        "img_key": "CAT_WEB",
    },

    # 4) TÊN MIỀN
    {
        "cat_id": "DOMAIN",
        "title": "🌐 TÊN MIỀN",
        "desc": (
            "🌐 **TÊN MIỀN – 370K / 1 domain**\n"
            "✅ Bảo hành suốt thời gian sử dụng\n"
            "✅ Đổi hậu đài ~ 3 phút\n"
            "👉 Chọn mục bên dưới 👇"
        ),
        "items": [
            {
                "item_id": "DOMAIN_370",
                "group": "TÊN MIỀN",
                "name": "Tên miền đồng giá",
                "price": "370.000đ",
                "detail": (
                    "🌐 **Tên miền đồng giá 370K**\n\n"
                    "✅ Bảo hành suốt thời gian sử dụng\n"
                    "✅ Đổi hậu đài ~ 3 phút\n\n"
                    "📌 Khi mua, ghi rõ **đuôi** (.com/.net/...) và **keyword**."
                ),
                "require_hint": "Yêu cầu: đuôi/keyword"
            },
        ],
        "img_key": "CAT_DOMAIN",
    },

    # 5) STK MB BANK
    {
        "cat_id": "MB",
        "title": "🏦 STK MB BANK",
        "desc": "🏦 **TK MB Bank**\n💰 13K / 1 TK\n👉 Chọn mục bên dưới 👇",
        "items": [
            {
                "item_id": "MB_13K",
                "group": "MB BANK",
                "name": "TK MB Bank",
                "price": "13.000đ",
                "detail": "🏦 **TK MB Bank**\n💰 Giá: **13.000đ / 1 TK**\n📌 Dùng theo nhu cầu tạo tài khoản game",
                "require_hint": "Yêu cầu: SL"
            },
        ],
        "img_key": "CAT_MB",
    },

    # 6) OTP SĐT
    {
        "cat_id": "OTP",
        "title": "📲 OTP SĐT",
        "desc": "📲 **OTP SĐT đăng ký game**\n💰 7K / 1 OTP\n👉 Chọn mục bên dưới 👇",
        "items": [
            {
                "item_id": "OTP_7K",
                "group": "OTP",
                "name": "OTP SĐT đăng ký game",
                "price": "7.000đ",
                "detail": "📲 **OTP SĐT đăng ký game**\n💰 Giá: **7.000đ / 1 OTP**\n📌 Khi mua, ghi rõ nền tảng/game cần OTP.",
                "require_hint": "Yêu cầu: nền tảng/game"
            },
        ],
        "img_key": "CAT_OTP",
    },
]

CAT_BY_ID = {c["cat_id"]: c for c in CATALOG}
ITEM_BY_ID = {}
for c in CATALOG:
    for it in c.get("items", []):
        ITEM_BY_ID[it["item_id"]] = (c["cat_id"], it)

# =========================
# UI (menu chính 2 cột)
# =========================
def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=2)
    # 6 mục, 2 cột
    kb.add(
        types.InlineKeyboardButton("📱 TELE", callback_data="CAT|TELE"),
        types.InlineKeyboardButton("📘 FACEBOOK", callback_data="CAT|FB"),
        types.InlineKeyboardButton("🖥️ LÀM WEB", callback_data="CAT|WEB"),
        types.InlineKeyboardButton("🌐 TÊN MIỀN", callback_data="CAT|DOMAIN"),
        types.InlineKeyboardButton("🏦 STK MB BANK", callback_data="CAT|MB"),
        types.InlineKeyboardButton("📲 OTP SĐT", callback_data="CAT|OTP"),
    )
    # hàng phụ
    kb.add(
        types.InlineKeyboardButton("💳 Thanh toán", callback_data="PAY"),
        types.InlineKeyboardButton("📩 Admin", url=admin_url()),
    )
    return kb

def kb_category(cat_id: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    cat = CAT_BY_ID.get(cat_id)
    if not cat:
        kb.add(types.InlineKeyboardButton("⏪ Quay lại", callback_data="BACK_MAIN"))
        return kb

    for it in cat.get("items", []):
        label = f"{it['name']} | {it['price']}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"ITEM|{it['item_id']}"))

    kb.add(types.InlineKeyboardButton("💳 Thanh toán", callback_data="PAY"))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại menu", callback_data="BACK_MAIN"))
    return kb

def kb_item(item_id: str, buy_url: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    # MUA NGAY: mở chat admin + text có sẵn
    kb.add(types.InlineKeyboardButton("✅ MUA NGAY (soạn sẵn)", url=buy_url))
    kb.add(types.InlineKeyboardButton("💳 Thanh toán", callback_data="PAY"))
    kb.add(types.InlineKeyboardButton("📩 Nhắn Admin", url=admin_url()))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại danh mục", callback_data=f"BACKCAT|{item_id}"))
    return kb

def kb_payment():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📩 Gửi bill cho Admin", url=admin_url()))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại menu", callback_data="BACK_MAIN"))
    return kb

# =========================
# Text
# =========================
def text_start():
    return (
        f"👋 **Chào mừng bạn đến với {SHOP_NAME}**\n\n"
        "✅ Bảng giá rõ ràng – hỗ trợ nhanh – xử lý gọn\n"
        "👉 Chọn danh mục bên dưới 👇"
    )

def text_payment():
    return (
        f"💳 **THÔNG TIN THANH TOÁN – {SHOP_NAME}**\n\n"
        f"🏦 **Ngân hàng:** Vietcombank ({BANK_NAME})\n"
        f"👤 **Chủ TK:** {ACCOUNT_NAME}\n"
        f"🔢 **STK:** {ACCOUNT_NO}\n\n"
        "✅ **NỘI DUNG CHUYỂN KHOẢN (BẮT BUỘC):**\n"
        "`@username + TÊN SẢN PHẨM`\n\n"
        "📌 Chuyển xong, chụp bill gửi admin để xác nhận nhanh."
    )

def category_message(cat_id: str):
    cat = CAT_BY_ID.get(cat_id)
    if not cat:
        return "❌ Danh mục không tồn tại."
    return f"**{cat['title']}**\n\n{cat['desc']}"

def item_message(item_id: str):
    found = ITEM_BY_ID.get(item_id)
    if not found:
        return "❌ Sản phẩm không tồn tại."
    _, it = found
    return f"✅ **{it['name']}**\n💰 **Giá:** **{it['price']}**\n\n{it['detail']}"

def build_buy_text(from_user, group: str, product: str, price: str, require_hint: str):
    # cú pháp theo yêu cầu user
    # MUA | [NHÓM] | [SẢN PHẨM] | SL: [x] |  GIÁ | Yêu cầu: [...]
    u = user_tag(from_user)
    return f"MUA | {group} | {product} | SL: 1 | {price} | Yêu cầu: {require_hint} | User: {u}"

# =========================
# Commands: /start /getid /setimg /listkeys
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    send_with_optional_photo(message.chat.id, "START", text_start(), reply_markup=kb_main())

@bot.message_handler(commands=["getid"])
def cmd_getid(message):
    bot.send_message(
        message.chat.id,
        "📌 **/getid**: Gửi **1 ảnh** vào đây, bot sẽ trả `file_id`.\n\n"
        "Admin gắn ảnh theo KEY bằng:\n"
        "`/setimg KEY`\n"
        "Xem KEY: `/listkeys`",
        parse_mode="Markdown",
    )

@bot.message_handler(commands=["listkeys"])
def cmd_listkeys(message):
    keys = ["START", "PAYMENT"]
    for c in CATALOG:
        keys.append(f"CAT_{c['cat_id']}")
        for it in c.get("items", []):
            keys.append(f"ITEM_{it['item_id']}")
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

    # luôn trả file_id
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
            img_key = f"CAT_{cat_id}"
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_category(cat_id))
            return

        if data.startswith("ITEM|"):
            item_id = data.split("|", 1)[1]
            found = ITEM_BY_ID.get(item_id)
            if not found:
                bot.send_message(chat_id, "❌ Sản phẩm không tồn tại.")
                return
            _, it = found

            text = item_message(item_id)

            buy_text = build_buy_text(
                call.from_user,
                group=it["group"],
                product=it["name"],
                price=it["price"],
                require_hint=it.get("require_hint", "...")
            )
            buy_url = build_prefilled_admin_link(buy_text)

            img_key = f"ITEM_{item_id}"
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_item(item_id, buy_url))
            return

        if data.startswith("BACKCAT|"):
            item_id = data.split("|", 1)[1]
            found = ITEM_BY_ID.get(item_id)
            if not found:
                send_with_optional_photo(chat_id, "START", text_start(), reply_markup=kb_main())
                return
            cat_id, _ = found
            text = category_message(cat_id)
            img_key = f"CAT_{cat_id}"
            send_with_optional_photo(chat_id, img_key, text, reply_markup=kb_category(cat_id))
            return

        bot.send_message(chat_id, "❓ Không hiểu thao tác. Gõ /start để bắt đầu lại.")

    except Exception as e:
        try:
            bot.send_message(call.message.chat.id, f"⚠️ Có lỗi nhỏ xảy ra.\nChi tiết: {e}")
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
