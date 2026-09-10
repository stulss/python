# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import threading
from pathlib import Path

BASE_DIR = Path(r"D:\stuls\python\_8_cafe_story")
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not Path(CHROME_PATH).exists():
    CHROME_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PORT = 5055
os.environ["FLASK_PORT"] = str(PORT)

from app import app
from db import init_db, get_db_connection

def run_server():
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

def capture(url, out_filename, delay=2.0):
    out_path = SCREENSHOTS_DIR / out_filename
    print(f"[Capture] Capturing {url} -> {out_filename}")
    cmd = [
        CHROME_PATH,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--virtual-time-budget=4000",
        "--window-size=1280,850",
        f"--screenshot={str(out_path)}",
        url
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(delay)
    if out_path.exists():
        print(f"  -> SUCCESS ({out_path.stat().st_size} bytes)")
    else:
        print(f"  -> FAILED to create {out_filename}")

def main():
    print("[DB] Initializing database...")
    init_db()

    # Ensure clean nicknames and test accounts
    conn = get_db_connection()
    with conn.cursor() as c:
        c.execute("UPDATE cafe_users SET nickname = %s, role_level = 2 WHERE username = 'admin'", ("카페운영자",))
        c.execute("UPDATE cafe_users SET nickname = %s, role_level = 1 WHERE username = 'golduser'", ("골드바리스타",))
        c.execute("UPDATE cafe_users SET nickname = %s, role_level = 0 WHERE username = 'user1'", ("새싹원두",))
        conn.commit()
    conn.close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2.5) # Wait for server ready

    base_url = f"http://127.0.0.1:{PORT}"

    # 1. 일반회원(user1) 헤더 & 메인 화면 (로그인 유저명, 권한 표기 확인)
    capture(f"{base_url}/switch-account?user=user1&next=/", "01_user_header_main.png")

    # 2. 일반회원(user1)이 골드 라운지(/gold) 접근 시도 -> 403 예외화면
    capture(f"{base_url}/switch-account?user=user1&next=/gold", "02_user_access_gold_denied.png")

    # 3. 일반회원(user1)이 관리자 페이지(/admin) 접근 시도 -> 403 예외화면
    capture(f"{base_url}/switch-account?user=user1&next=/admin", "03_user_access_admin_denied.png")

    # 4. 골드회원(golduser)이 골드 라운지(/gold) 정상 접근 성공 화면
    capture(f"{base_url}/switch-account?user=golduser&next=/gold", "04_gold_access_gold_success.png")

    # 5. 골드회원(golduser)이 관리자 페이지(/admin) 접근 시도 -> 403 예외화면
    capture(f"{base_url}/switch-account?user=golduser&next=/admin", "05_gold_access_admin_denied.png")

    # 6. 관리자(admin)가 관리자 센터(/admin) 정상 접근 성공 화면 (회원 목록, 등급 수정, 삭제 버튼)
    capture(f"{base_url}/switch-account?user=admin&next=/admin", "06_admin_access_admin_success.png")

    print("\n[COMPLETE] All screenshots captured in screenshots/ directory!")

if __name__ == "__main__":
    main()