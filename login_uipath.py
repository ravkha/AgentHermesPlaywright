import time
import pickle
import os
import glob
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from datetime import datetime

# Load environment variables from .env
load_dotenv()

# Validate required environment variables
UIPATH_EMAIL = os.getenv("UIPATH_EMAIL")
UIPATH_PASS = os.getenv("UIPATH_PASS")
if not UIPATH_EMAIL or not UIPATH_PASS:
    raise ValueError("❌ UIPATH_EMAIL dan UIPATH_PASS harus diatur di file .env")

# Dynamic session file name (matches script name: login_uipath.py -> login_uipath.pkl)
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]
COOKIE_FILE = f"{SCRIPT_NAME}.pkl"

# Directories and URLs
TEMPIMG_DIR = "tempimg"
BASE_URL = "https://cloud.uipath.com"
TARGET_URL = "https://cloud.uipath.com/diamojslkvou/DiamondGroupDefault/orchestrator_/jobs?tid=902&fid=2046466"

def cleanup_tempimg():
    """Buat folder tempimg jika belum ada, lalu hapus semua gambar di dalamnya"""
    os.makedirs(TEMPIMG_DIR, exist_ok=True)
    image_extensions = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp")
    for ext in image_extensions:
        for img_file in glob.glob(os.path.join(TEMPIMG_DIR, ext)):
            try:
                os.remove(img_file)
            except: pass
    print(f"🧹 Folder {TEMPIMG_DIR} dibersihkan dari semua gambar")

def save_failure_screenshot(page, context_name="failure"):
    """Simpan screenshot ke folder tempimg saat terjadi kegagalan"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(TEMPIMG_DIR, f"{context_name}_{timestamp}.png")
    try:
        page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot disimpan: {screenshot_path}")
    except Exception as e:
        print(f"⚠️ Gagal mengambil screenshot: {e}")

def perform_login(browser_context, page):
    """Proses login inti"""
    print("🚀 Memulai proses login...")
    try:
        # 1. Klik 'Continue with email'
        print("   - Menunggu tombol 'continue with email'...")
        btn_email = page.wait_for_selector('button:has-text("continue with email")', timeout=15000)
        if btn_email:
            btn_email.click()
            print("   - Klik 'Continue with email' berhasil")
        
        # 2. Isi Email
        print(f"   - Mengisi email: {UIPATH_EMAIL}")
        page.wait_for_selector('input[name="email"]', timeout=10000).fill(UIPATH_EMAIL)
        
        # 3. Isi Password
        print("   - Mengisi password...")
        page.fill('input[name="password"]', UIPATH_PASS)
        
        # 4. Submit
        print("   - Klik submit...")
        page.click('button[type="submit"]')
        
        # 5. Tunggu sampai masuk ke portal atau cloud uipath
        print("   - Menunggu verifikasi dashboard...")
        try:
            page.wait_for_url(lambda url: "portal_" in url or "cloud.uipath.com" in url, timeout=45000)
        except:
            print("   - Timeout wait_for_url, tapi mencoba lanjut cek cookies...")
        
        # 6. Simpan Cookies
        cookies = browser_context.cookies()
        if any(c['name'] == 'ai_user' or 'uipath' in c['domain'] for c in cookies):
            with open(COOKIE_FILE, "wb") as f:
                pickle.dump(cookies, f)
            print(f"✅ Login sukses! Sesi disimpan ke {COOKIE_FILE}")
            return True
        else:
            print("❌ Tidak ditemukan cookies sesi yang valid.")
            return False
        
    except Exception as e:
        print(f"❌ Proses login gagal: {e}")
        save_failure_screenshot(page, "login_error")
        return False

def run():
    cleanup_tempimg()
    
    with sync_playwright() as p:
        # Launch browser with specific flags for stability
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # 1. Load Cookies jika ada
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, "rb") as f:
                    context.add_cookies(pickle.load(f))
                print(f"🔄 Memuat sesi lama dari {COOKIE_FILE}")
            except Exception as e:
                print(f"⚠️ Gagal memuat cookie: {e}")

        # 2. Buka Target URL
        print(f"🌍 Membuka URL: {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) # Tunggu redirect
        except Exception as e:
            print(f"❌ Gagal memuat halaman: {e}")
            save_failure_screenshot(page, "load_fail")
            browser.close()
            return

        # 3. Cek Status Login
        # Tunggu sebentar untuk memastikan redirect selesai
        time.sleep(3)
        
        is_login_page = "account.uipath.com" in page.url
        login_button = None
        try:
            # Gunakan selector yang lebih ringan untuk cek tombol
            login_button = page.locator('button:has-text("continue with email")').first
            is_button_visible = login_button.is_visible(timeout=5000)
        except:
            is_button_visible = False
        
        if is_login_page or is_button_visible:
            print("🔐 Terdeteksi halaman login.")
            # Coba handle cookie banner dulu kalau ada
            try: page.click('button:has-text("Accept All")', timeout=3000)
            except: pass
            
            if not perform_login(context, page):
                print("❌ Gagal login, menghentikan script.")
                browser.close()
                return
            
            # Kembali ke Target URL setelah login
            print(f"🔄 Kembali ke target: {TARGET_URL}")
            page.goto(TARGET_URL, wait_until="networkidle")
        else:
            print("✅ Sesi masih aktif, lanjut ke tahap berikutnya.")

        # 4. Tunggu UI Orchestrator
        print("⏳ Menunggu UI Orchestrator (20s)...")
        time.sleep(20)

        # 5. Navigasi ke Foreground
        try:
            print("📂 Mencari tab/folder Foreground...")
            # Coba beberapa metode selector untuk Foreground
            foreground = None
            selectors = [
                'text="Foreground"',
                'span:has-text("Foreground")',
                '.uip-menu-item-label:has-text("Foreground")',
                'div[role="button"]:has-text("Foreground")'
            ]
            
            for sel in selectors:
                try:
                    foreground = page.wait_for_selector(sel, timeout=5000)
                    if foreground:
                        print(f"✅ Menemukan Foreground dengan selector: {sel}")
                        break
                except: continue
                
            if foreground:
                foreground.click()
                print("✅ Tab Foreground diklik")
                time.sleep(10)
            else:
                print("⚠️ Tidak dapat menemukan elemen 'Foreground', mencoba reload...")
                page.reload()
                time.sleep(15)
        except Exception as e:
            print(f"⚠️ Gagal navigasi ke Foreground: {e}")
            save_failure_screenshot(page, "nav_foreground_fail")

        # 6. Scrape Data Jobs
        print("📊 Mengambil data Jobs...")
        # Tambahkan retry untuk scraping tabel
        for attempt in range(3):
            try:
                # Tunggu minimal satu row muncul
                page.wait_for_selector("tr.ui-grid-row", timeout=15000)
                rows = page.query_selector_all("tr.ui-grid-row")
                if rows: break
            except:
                print(f"   (Percobaan {attempt+1}) Menunggu tabel data...")
                time.sleep(5)
        
        try:
            rows = page.query_selector_all("tr.ui-grid-row")
            all_jobs = []
            
            print(f"   🔍 Ditemukan {len(rows)} baris data.")
            for row in rows:
                cells = row.query_selector_all(".ui-grid-cell-contents")
                if len(cells) >= 11:
                    process = cells[0].inner_text().strip()
                    state = cells[2].inner_text().strip()
                    started = cells[3].inner_text().strip()
                    host = cells[10].inner_text().strip()
                    
                    all_jobs.append({
                        "proc": process,
                        "state": state,
                        "time": started,
                        "host": host
                    })

            # Filter 10 Sukses Terbaru
            success_jobs = [j for j in all_jobs if j["state"].lower() == "successful"][:10]
            
            # Filter 10 Failed/Stopped Terbaru
            failed_states = ["faulted", "stopped", "failed"]
            failed_jobs = [j for j in all_jobs if j["state"].lower() in failed_states][:10]

            print("\n--- LAPORAN RPA FOREGROUND (GROUPED BY STATE) ---")
            
            print("\n🔴 FAILED/STOPPED (Top 10):")
            if not failed_jobs:
                print("   ✅ Tidak ada job failed.")
            else:
                for j in failed_jobs:
                    print(f"   - [{j['state']}] {j['proc']} @ {j['host']} ({j['time']})")

            print("\n🟢 SUCCESSFUL (Top 10):")
            if not success_jobs:
                print("   ⚠️ Tidak ada job sukses ditemukan di row awal.")
            else:
                for j in success_jobs:
                    print(f"   - [{j['state']}] {j['proc']} @ {j['host']} ({j['time']})")
            
            print(f"\nSelesai pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            page.screenshot(path="uipath_report.png")
            
        except Exception as e:
            print(f"❌ Gagal mengambil data: {e}")
            save_failure_screenshot(page, "scrape_fail")

        browser.close()

if __name__ == "__main__":
    run()
