# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\stuls\python\_8_cafe_story")
from db import get_db_connection

conn = get_db_connection()
with conn.cursor() as c:
    c.execute("SELECT id, username, nickname, role_level, created_at FROM cafe_users ORDER BY id ASC")
    rows = c.fetchall()

    role_map = {0: "일반회원 (0)", 1: "골드회원 (1)", 2: "관리자 (2)"}

    header = f"{'ID':<4} | {'아이디(username)':<16} | {'닉네임(nickname)':<14} | {'권한등급(role_level)':<18} | {'가입일시':<19}"
    print("=" * len(header))
    print(header)
    print("=" * len(header))
    for r in rows:
        r_name = role_map.get(r['role_level'], str(r['role_level']))
        print(f"{r['id']:<4} | {r['username']:<16} | {r['nickname']:<14} | {r_name:<18} | {str(r['created_at'])[:19]:<19}")
    print("=" * len(header))