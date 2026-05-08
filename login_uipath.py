import time
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
import glob
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import socket
from datetime import datetime

# Load environment variables from .env
load_dotenv()

# Validate required environment variables
UIPATH_EMAIL = os.getenv("UIPATH_EMAIL")
UIPATH_PASS = os.getenv("UIPATH_PASS")
if not UIPATH_EMAIL or not UIPATH_PASS:
    raise ValueError("❌ UIPATH_EMAIL dan UIPATH_PASS harus diatur di file .env")

SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]

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
            except:
                pass
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
        btn_email = page.wait_for_selector(
            'button:has-text("continue with email")', timeout=15000
        )
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
            page.wait_for_url(
                lambda url: "portal_" in url or "cloud.uipath.com" in url, timeout=45000
            )
        except:
            print("   - Timeout wait_for_url, tapi mencoba lanjut cek cookies...")

        # 6. Cek Sesi (Cookies)
        cookies = browser_context.cookies()
        if any(c["name"] == "ai_user" or "uipath" in c["domain"] for c in cookies):
            print("✅ Login sukses!")
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
    hostname = socket.gethostname()
    if "ubuntu" in hostname:
        var_headless = True
    else:
        var_headless = False

    with sync_playwright() as p:
        # Launch browser with specific flags for stability
        browser = p.chromium.launch(
            headless=var_headless, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        # 1. Buat Context Baru
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # 2. Buka Target URL
        print(f"🌍 Membuka URL: {TARGET_URL}")
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"⚠️ Peringatan goto awal: {e}")

        # 3. Selalu Lakukan Login
        print("🔐 Memulai proses login...")
        # Klik Accept All cookies jika muncul
        try:
            page.click('button:has-text("Accept All")', timeout=3000)
        except:
            pass

        if not perform_login(context, page):
            print("❌ Gagal login, menghentikan script.")
            browser.close()
            return

        # Beri jeda setelah login agar sesi benar-benar settle
        print("⏳ Menunggu sesi sinkronisasi...")
        time.sleep(5)

        # Pastikan berada di target URL setelah login
        if "orchestrator_" not in page.url:
            print(f"🔄 Kembali ke target: {TARGET_URL}")
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)
            except Exception as e:
                print(f"⚠️ Peringatan navigasi setelah login: {e}")

        # 4. Tunggu UI Orchestrator
        print("⏳ Menunggu UI Orchestrator (elemen 'Tenant ')...")
        try:
            page.wait_for_selector('span:has-text("Tenant ")', timeout=60000)
            print("✅ Elemen 'Tenant ' ditemukan.")
        except Exception as e:
            print(f"⚠️ Gagal menunggu elemen 'Tenant ': {e}")
        time.sleep(5)

        # 5. Navigasi ke Foreground
        try:
            print("📂 Mencari tab/folder Foreground...")
            # Coba beberapa metode selector untuk Foreground
            foreground = None
            selectors = [
                'text="Foreground"',
                'span:has-text("Foreground")',
                '.uip-menu-item-label:has-text("Foreground")',
                'div[role="button"]:has-text("Foreground")',
            ]

            for sel in selectors:
                try:
                    foreground = page.wait_for_selector(sel, timeout=5000)
                    if foreground:
                        print(f"✅ Menemukan Foreground dengan selector: {sel}")
                        break
                except:
                    continue

            if foreground:
                foreground.click()
                print("✅ Tab Foreground diklik")
                time.sleep(5)

                # 5.5. Tunggu tabel dimuat
                # 5.5. Tunggu tabel dimuat (tambah jeda sesuai saran user)
                print("⏳ Menunggu tabel data memuat...")
                time.sleep(10)
            else:
                print("⚠️ Tidak dapat menemukan elemen 'Foreground', mencoba reload...")
                page.reload()
                time.sleep(15)
        except Exception as e:
            print(f"⚠️ Gagal navigasi ke Foreground: {e}")
            save_failure_screenshot(page, "nav_foreground_fail")

        # 6. Scrape Data Jobs (menggunakan ui-grid selector UiPath)
        print("📊 Mengambil 25 data Jobs terbaru...")
        all_jobs = []

        for scrape_attempt in range(
            5
        ):  # Beri kesempatan 5 kali (sekitar 25-30 detik total)
            try:
                # 1. Tunggu row muncul
                page.wait_for_selector(".ui-grid-row", timeout=20000)

                # 2. Tunggu sampai salah satu cell berisi teks
                try:
                    page.wait_for_function(
                        '() => Array.from(document.querySelectorAll(".ui-grid-cell-contents")).some(el => el.innerText.trim().length > 0)',
                        timeout=10000,
                    )
                except:
                    pass

                # 3. Identifikasi Index Kolom berdasarkan Header
                header_cells = page.locator(".ui-grid-header-cell .ui-grid-header-cell-label").all_inner_texts()
                header_cells = [h.strip() for h in header_cells]
                
                # Mapping header ke index
                idx_map = {
                    "proc":  next((i for i, h in enumerate(header_cells) if "Process" in h), 1),
                    "state": next((i for i, h in enumerate(header_cells) if "State" in h), 2),
                    "ended": next((i for i, h in enumerate(header_cells) if "Ended" in h), 5),
                    "host":  next((i for i, h in enumerate(header_cells) if "Hostname" in h), 11)
                }
                
                if scrape_attempt == 0:
                    print(f"   📊 Column Mapping: {idx_map}")

                # 4. Ambil data baris
                rows = page.locator(".ui-grid-row").all()[:25]
                current_batch = []

                for row in rows:
                    cells_locator = row.locator(".ui-grid-cell-contents")
                    if cells_locator.count() == 0:
                        cells_locator = row.locator(".ui-grid-cell")

                    cells = [c.strip() for c in cells_locator.all_inner_texts()]

                    if len(cells) > max(idx_map.values()):
                        current_batch.append(
                            {
                                "proc":  cells[idx_map["proc"]],
                                "state": cells[idx_map["state"]],
                                "ended": cells[idx_map["ended"]],
                                "host":  cells[idx_map["host"]],
                            }
                        )

                # Cek apakah ada hostname yang "N/A" atau kosong
                # Jika ada minimal satu job tapi hostnamenya masih N/A atau kosong, kita tunggu lagi
                if current_batch:
                    # Filter job yang benar-benar punya data (nama proses tidak kosong)
                    valid_jobs = [j for j in current_batch if j["proc"]]
                    if valid_jobs:
                        has_na = any(
                            not j["host"]
                            or j["host"].upper() == "N/A"
                            or j["host"] == "-"
                            for j in valid_jobs
                        )
                        if not has_na:
                            all_jobs = valid_jobs
                            print("   ✅ Semua hostname terdeteksi.")
                            break
                        else:
                            print(
                                f"   ⏳ Hostname masih N/A/Kosong, menunggu loading tambahan... (Percobaan {scrape_attempt+1})"
                            )
                            time.sleep(5)
                            all_jobs = valid_jobs  # Simpan dulu buat jaga-jaga kalau timeout terus
                    else:
                        print(
                            f"   ⏳ Data baris masih kosong, menunggu... (Percobaan {scrape_attempt+1})"
                        )
                        time.sleep(5)
                else:
                    print(
                        f"   ⏳ Tabel belum muncul, menunggu... (Percobaan {scrape_attempt+1})"
                    )
                    time.sleep(5)

            except Exception as e:
                print(f"   ⚠️ Error saat mencoba mengambil data: {e}")
                time.sleep(5)

        try:
            if not all_jobs:
                print("⚠️ Tidak ada data job yang berhasil diambil.")
                return

            # 4. Kelompokkan berdasarkan Hostname
            grouped_jobs = {}
            for j in all_jobs:
                h = j["host"]
                if h not in grouped_jobs:
                    grouped_jobs[h] = []
                grouped_jobs[h].append(j)

            print("\n--- LAPORAN RPA FOREGROUND (GROUPED BY HOSTNAME) ---")
            for host, jobs in grouped_jobs.items():
                print(f"\n{host}")
                print("JobName,State,Ended")
                for j in jobs:
                    print(f"{j['proc']},{j['state']},{j['ended']}")

            print(f"\nSelesai pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            page.screenshot(path="uipath_report.png")

        except Exception as e:
            print(f"❌ Gagal mengambil data: {e}")
            save_failure_screenshot(page, "scrape_fail")

        browser.close()


if __name__ == "__main__":
    run()
