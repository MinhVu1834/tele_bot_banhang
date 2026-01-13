import os
import sqlite3
import random
import threading
import time
from datetime import datetime

import telebot
from telebot import types
from flask import Flask, request

# =========================
# CONFIG (ENV)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@min_max1834").strip()

BANK_NAME = os.getenv("BANK_NAME", "VCB").strip()
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME", "A HI HI").strip()
ACCOUNT_NO = os.getenv("ACCOUNT_NO", "0311000742866").strip()

PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "orders.db")

SHOP_NAME = "SHOP X"

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN env var")

# =========================
# PRODUCTS (Stage 1)
# =========================
PRODUCTS = [
    {"code": "SESSION1", "price": 12000, "stock": 346, "active": True},
    {"code": "SESSION55", "price": 28000, "stock": 0, "active": False},
    {"code": "SESSION86", "price": 26000, "stock": 35, "active": True},
    {"code": "SESSION +855", "price": 28000, "stock": 55, "active": True},
]

# =========================
# DB (SQLite)
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
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            username TEXT,
            product_code TEXT NOT NULL,
            qty INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def order_exists(order_id: str) -> bool:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM orders WHERE order_id = ? LIMIT 1", (order_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def create_order(chat_id: int, username: str, product_code: str, qty: int, amount: int) -> str:
    for _ in range(30):
        order_id = f"DH{random.randint(10000, 99999)}"
        if not order_exists(order_id):
            conn = db_connect()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO orders(order_id, chat_id, username, product_code, qty, amount, status, created_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (order_id, chat_id, username, product_code, qty, amount, "CREATED", datetime.utcnow().isoformat()),
            )
            conn.commit()
            conn.close()
            return order_id
    raise RuntimeError("Could not generate unique order_id")

def get_order(order_id: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE order_id = ? LIMIT 1", (order_id,))
    row = cur.fetchone()
    conn.close()
    return row

# =========================
# BOT + FLASK
# =========================
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
server = Flask(__name__)

def money_vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + "đ"

def admin_url() -> str:
    u = ADMIN_USERNAME.lstrip("@")
    return f"https://t.me/{u}"

def find_product(code: str):
    for p in PRODUCTS:
        if p["code"] == code:
            return p
    return None

# ==============
# Keyboards
# ==============
def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛒 Session", callback_data="MENU_SESSION"),
        types.InlineKeyboardButton("📩 Liên hệ Admin", url=admin_url()),
    )
    return kb

def kb_session_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for p in PRODUCTS:
        text = f'{p["code"]} | {money_vnd(p["price"])} | Còn: {p["stock"]}'
        kb.add(types.InlineKeyboardButton(text, callback_data=f"PROD|{p['code']}"))
    kb.add(types.InlineKeyboardButton("⏪ Quay Lại", callback_data="BACK_MAIN"))
    return kb

def kb_product_detail(code: str):
    kb = types.InlineKeyboardMarkup(row_width=2)
    p = find_product(code)
    if p and p["active"] and p["stock"] > 0:
        kb.add(types.InlineKeyboardButton("✅ MUA NGAY", callback_data=f"BUY|{code}"))
    kb.add(
        types.InlineKeyboardButton("⏪ Quay Lại", callback_data="MENU_SESSION"),
        types.InlineKeyboardButton("📩 Admin", url=admin_url()),
    )
    return kb

def kb_order_created(order_id: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📩 NHẮN ADMIN", url=admin_url()))
    kb.add(types.InlineKeyboardButton("💳 LẤY THÔNG TIN THANH TOÁN", callback_data=f"PAY|{order_id}"))
    kb.add(types.InlineKeyboardButton("🛒 Mua thêm", callback_data="MENU_SESSION"))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại", callback_data="BACK_MAIN"))
    return kb

def kb_payment(order_id: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📩 GỬI BILL CHO ADMIN", url=admin_url()))
    kb.add(types.InlineKeyboardButton("⏪ Quay lại", callback_data=f"ORDER|{order_id}"))
    return kb

# ==============
# Bot messages
# ==============
@bot.message_handler(commands=["start"])
def start_cmd(message):
    text = (
        f"👋 **Chào mừng bạn đến với {SHOP_NAME}**\n\n"
        "⚡ Hàng sẵn – giao nhanh – hỗ trợ tận tình\n"
        "🛡️ Uy tín – rõ ràng – xử lý nhanh gọn\n\n"
        "👉 Vui lòng chọn dịch vụ bên dưới 👇"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb_main())

def send_session_menu(chat_id: int):
    bot.send_message(chat_id, "🛒 **Session – Chọn dịch vụ**", parse_mode="Markdown", reply_markup=kb_session_menu())

def send_product_detail(chat_id: int, code: str):
    p = find_product(code)
    if not p:
        bot.send_message(chat_id, "❌ Sản phẩm không tồn tại.", reply_markup=kb_session_menu())
        return

    if p["stock"] <= 0 or not p["active"]:
        text = (
            f"❌ **{p['code']} hiện đã hết hàng**\n\n"
            "📩 Nhắn admin để được báo khi có hàng hoặc tư vấn dịch vụ khác."
        )
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("📩 Liên hệ Admin", url=admin_url()))
        kb.add(types.InlineKeyboardButton("⏪ Quay Lại", callback_data="MENU_SESSION"))
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
        return

    text = (
        f"✅ **{p['code']}**\n\n"
        f"💰 **Giá:** {money_vnd(p['price'])} / 1\n"
        "⚡ **Giao hàng:** 5–15 phút sau khi xác nhận thanh toán\n"
        "🛡️ **Cam kết:** Hỗ trợ nếu phát sinh lỗi\n\n"
        "👉 Nhấn **MUA NGAY** để tạo đơn tự động 👇"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb_product_detail(code))

def send_order_created(chat_id: int, order_id: str):
    row = get_order(order_id)
    if not row:
        bot.send_message(chat_id, "❌ Không tìm thấy đơn hàng.")
        return

    username = row["username"] or "username"

    text = (
        "✅ **TẠO ĐƠN THÀNH CÔNG**\n\n"
        f"🧾 **Mã đơn:** **{row['order_id']}**\n"
        f"📦 **Sản phẩm:** {row['product_code']}\n"
        f"💰 **Số tiền:** {money_vnd(row['amount'])}\n\n"
        "👉 Bước tiếp theo: Nhắn admin để được xử lý nhanh ⚡\n\n"
        "**📋 MẪU NHẮN ADMIN (COPY):**\n"
        f"`MUA {row['order_id']} | {row['product_code']} | SL: {row['qty']} | Telegram: @{username}`"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb_order_created(order_id))

def send_payment_info(chat_id: int, order_id: str):
    row = get_order(order_id)
    if not row:
        bot.send_message(chat_id, "❌ Không tìm thấy đơn hàng.")
        return

    text = (
        f"💳 **THÔNG TIN THANH TOÁN – {SHOP_NAME}**\n\n"
        f"🏦 **Ngân hàng:** Vietcombank ({BANK_NAME})\n"
        f"👤 **Chủ tài khoản:** {ACCOUNT_NAME}\n"
        f"🔢 **Số tài khoản:** {ACCOUNT_NO}\n\n"
        "✅ **NỘI DUNG CHUYỂN KHOẢN (BẮT BUỘC):**\n"
        f"**{row['order_id']}**\n\n"
        "📌 Sau khi chuyển khoản, vui lòng **chụp bill** và gửi admin kèm nội dung:\n"
        f"`ĐÃ CK {row['order_id']} | {money_vnd(row['amount'])}`"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb_payment(order_id))

@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        data = call.data
        chat_id = call.message.chat.id
        bot.answer_callback_query(call.id)

        if data == "BACK_MAIN":
            bot.send_message(chat_id, "🏠 **Menu chính**", parse_mode="Markdown", reply_markup=kb_main())
            return

        if data == "MENU_SESSION":
            send_session_menu(chat_id)
            return

        if data.startswith("PROD|"):
            code = data.split("|", 1)[1]
            send_product_detail(chat_id, code)
            return

        if data.startswith("BUY|"):
            code = data.split("|", 1)[1]
            p = find_product(code)
            if not p or p["stock"] <= 0 or not p["active"]:
                bot.send_message(chat_id, "❌ Sản phẩm đang hết hàng.", reply_markup=kb_session_menu())
                return

            username = call.from_user.username or ""
            qty = 1
            amount = int(p["price"]) * qty

            order_id = create_order(chat_id, username, code, qty, amount)
            send_order_created(chat_id, order_id)
            return

        if data.startswith("PAY|"):
            order_id = data.split("|", 1)[1]
            send_payment_info(chat_id, order_id)
            return

        if data.startswith("ORDER|"):
            order_id = data.split("|", 1)[1]
            send_order_created(chat_id, order_id)
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
    # Log ping for visibility in Render logs
    if request.path in ("/", "/health"):
        print(f"[PING] {datetime.utcnow().isoformat()} from={request.headers.get('X-Forwarded-For','')} ua={request.headers.get('User-Agent','')}")

# =========================
# Run polling in a background thread
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
