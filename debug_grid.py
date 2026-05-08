import os, sys, time, json
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
STATE_FILE = "login_uipath_state.json"
TARGET_URL = "https://cloud.uipath.com/diamojslkvou/DiamondGroupDefault/orchestrator_/jobs?tid=902&fid=2046466"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--no-sandbox'])
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        storage_state=STATE_FILE
    )
    page = context.new_page()
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

    # Tunggu Tenant muncul
    page.wait_for_selector('span:has-text("Tenant ")', timeout=60000)

    # Klik Foreground
    page.locator('text="Foreground"').first.click()
    print("✅ Foreground diklik, tunggu 5 detik...")
    time.sleep(5)

    # Dump HTML grid area ke file untuk analisa
    grid_html = page.locator(".ui-grid-viewport").first.inner_html()
    with open("debug_grid.html", "w", encoding="utf-8") as f:
        f.write(grid_html[:50000])  # Simpan 50KB pertama
    print("✅ HTML grid disimpan ke debug_grid.html")

    # Cetak semua class yang dipakai di dalam grid row pertama
    first_row = page.locator(".ui-grid-row").first
    html_row = first_row.inner_html()
    print(f"\n📋 HTML baris pertama (500 char):\n{html_row[:500]}")

    browser.close()
    print("\nSelesai!")
