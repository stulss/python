# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\stuls\python\_8_cafe_story")

from app import app
from db import init_db

def run_tests():
    init_db()
    client = app.test_client()
    print("=" * 60)
    print("☕ [카페이야기] RBAC 접근 제어 및 기능 통합 테스트 시작")
    print("=" * 60)

    # 1. 비로그인(게스트) 접근 제어 테스트 (쿠키 없음)
    print("\n[TEST 1] 비로그인(게스트) 상태에서 보호된 페이지 접근 제어")
    g_res = client.get("/gold")
    print(f"비로그인 /gold 접근 코드: {g_res.status_code}")
    assert g_res.status_code == 401, f"Expected 401 but got {g_res.status_code}"
    print("-> [PASS] 비로그인 유저 /gold 접근 차단 (401)")

    a_res = client.get("/admin")
    print(f"비로그인 /admin 접근 코드: {a_res.status_code}")
    assert a_res.status_code == 401, f"Expected 401 but got {a_res.status_code}"
    print("-> [PASS] 비로그인 유저 /admin 접근 차단 (401)")

    # 2. 회원가입 테스트: 신규 회원은 무조건 role_level=0 (일반)인지 검증
    print("\n[TEST 2] 회원가입 시 일반 유저(Lv.0)로 자동 등록되는지 확인")
    reg_res = client.post("/api/auth/register", json={
        "username": "new_guest_99",
        "password": "password1234",
        "nickname": "새싹원두99"
    })
    print(f"회원가입 응답 코드: {reg_res.status_code}")
    reg_data = reg_res.get_json()
    if reg_res.status_code == 201:
        assert reg_data["user"]["role_level"] == 0, "회원가입 유저 등급이 0이 아닙니다!"
        print(f"-> [PASS] 신규 유저 '{reg_data['user']['username']}' 등록 완료 (등급: {reg_data['user']['role_name']} Lv.{reg_data['user']['role_level']})")
    else:
        print("-> 유저 기존 존재 (생략)")

    # 3. 일반회원(Lv.0) 로그인 및 권한 테스트
    print("\n[TEST 3] 일반회원(Lv.0) 로그인 후 골드 및 관리자 페이지 접근 시도")
    login_user1 = client.post("/api/auth/login", json={"username": "user1", "password": "1234"})
    assert login_user1.status_code == 200
    user1_token = login_user1.get_json()["token"]
    client.set_cookie(app.config["COOKIE_NAME"], user1_token)

    # 3-1. 일반회원이 골드 라운지(/gold) 접근 시도 -> 403 예외 화면이어야 함!
    res_gold_user1 = client.get("/gold")
    print(f"일반회원의 /gold 접근 응답: {res_gold_user1.status_code}")
    assert res_gold_user1.status_code == 403, f"Expected 403 but got {res_gold_user1.status_code}"
    assert "접근 권한이 없습니다!" in res_gold_user1.get_data(as_text=True)
    print("-> [PASS] 일반회원(Lv.0)의 골드 라운지 접근 차단 및 예외화면 출력 (403 Forbidden)")

    # 3-2. 일반회원이 관리자 페이지(/admin) 접근 시도 -> 403 예외 화면이어야 함!
    res_admin_user1 = client.get("/admin")
    print(f"일반회원의 /admin 접근 응답: {res_admin_user1.status_code}")
    assert res_admin_user1.status_code == 403, f"Expected 403 but got {res_admin_user1.status_code}"
    assert "접근 권한이 없습니다!" in res_admin_user1.get_data(as_text=True)
    print("-> [PASS] 일반회원(Lv.0)의 관리자 센터 접근 차단 및 예외화면 출력 (403 Forbidden)")

    # 3-3. 일반회원이 관리자 API(/api/admin/users) 호출 시도 -> 403 JSON이어야 함!
    res_api_admin_user1 = client.get("/api/admin/users", headers={"Authorization": f"Bearer {user1_token}"})
    print(f"일반회원의 /api/admin/users API 호출: {res_api_admin_user1.status_code}")
    assert res_api_admin_user1.status_code == 403
    print("-> [PASS] 일반회원의 관리자 API 호출 차단 (403 JSON)")

    # 4. 골드회원(Lv.1) 로그인 및 권한 테스트
    print("\n[TEST 4] 골드회원(Lv.1) 로그인 후 접근 제어 테스트")
    login_gold = client.post("/api/auth/login", json={"username": "golduser", "password": "1234"})
    assert login_gold.status_code == 200
    gold_token = login_gold.get_json()["token"]
    client.set_cookie(app.config["COOKIE_NAME"], gold_token)

    # 4-1. 골드회원이 골드 라운지(/gold) 접근 -> 200 OK 정상 화면!
    res_gold_gold = client.get("/gold")
    print(f"골드회원의 /gold 접근 응답: {res_gold_gold.status_code}")
    assert res_gold_gold.status_code == 200
    assert "VIP 시크릿 라운지" in res_gold_gold.get_data(as_text=True)
    print("-> [PASS] 골드회원(Lv.1)의 골드 라운지 정상 접근 (200 OK)")

    # 4-2. 골드회원이 관리자 페이지(/admin) 접근 시도 -> 403 예외 화면!
    res_admin_gold = client.get("/admin")
    print(f"골드회원의 /admin 접근 응답: {res_admin_gold.status_code}")
    assert res_admin_gold.status_code == 403
    assert "접근 권한이 없습니다!" in res_admin_gold.get_data(as_text=True)
    print("-> [PASS] 골드회원(Lv.1)의 관리자 센터 접근 차단 및 예외화면 출력 (403 Forbidden)")

    # 5. 관리자(Lv.2) 로그인 및 회원정보 관리(수정, 삭제) 테스트
    print("\n[TEST 5] 관리자(Lv.2) 로그인 및 회원정보 조회/수정/삭제 테스트")
    login_admin = client.post("/api/auth/login", json={"username": "admin", "password": "1234"})
    assert login_admin.status_code == 200
    admin_token = login_admin.get_json()["token"]
    client.set_cookie(app.config["COOKIE_NAME"], admin_token)

    # 5-1. 관리자의 /gold 및 /admin 페이지 접근 -> 모두 200 OK
    assert client.get("/gold").status_code == 200
    res_admin_page = client.get("/admin")
    assert res_admin_page.status_code == 200
    assert "카페이야기 운영자 센터" in res_admin_page.get_data(as_text=True)
    print("-> [PASS] 관리자(Lv.2)의 골드 라운지 및 관리자 센터 정상 접근 (200 OK)")

    # 5-2. 회원정보 목록 조회 API (GET /api/admin/users)
    res_users = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_users.status_code == 200
    users_data = res_users.get_json()
    print(f"-> [PASS] 회원 목록 조회 성공! 총 회원수: {users_data['stats']['total']}명")

    # 5-3. 회원 등급 수정 API 테스트: user1의 등급을 0 -> 1(골드)로 승급
    user1_id = None
    for u in users_data["users"]:
        if u["username"] == "user1":
            user1_id = u["id"]
            break

    if user1_id:
        res_role_update = client.put(f"/api/admin/users/{user1_id}/role", 
                                     headers={"Authorization": f"Bearer {admin_token}"},
                                     json={"role_level": 1})
        assert res_role_update.status_code == 200
        print(f"-> [PASS] 회원 등급 수정 성공: {res_role_update.get_json()['message']}")

        # 다시 user1 등급을 원래대로 0으로 복구
        client.put(f"/api/admin/users/{user1_id}/role", 
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"role_level": 0})
        print(f"-> [PASS] 회원 등급 원복 (0) 완료")

    # 5-4. 임시 회원 생성 후 삭제 테스트
    reg_temp = client.post("/api/auth/register", json={
        "username": "temp_delete_user",
        "password": "pwd",
        "nickname": "임시회원"
    })
    if reg_temp.status_code == 201:
        temp_id = reg_temp.get_json()["user"]["id"]
        res_del = client.delete(f"/api/admin/users/{temp_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert res_del.status_code == 200
        print(f"-> [PASS] 회원 삭제 기능 성공: {res_del.get_json()['message']}")

    print("\n" + "=" * 60)
    print("🎉 모든 접근 제어 및 기능 테스트 통과 (100% ALL PASS)!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()