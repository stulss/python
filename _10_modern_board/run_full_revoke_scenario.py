import sys
import json
import urllib.request
import time
import subprocess

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run():
    print("=" * 70, flush=True)
    print(" [1단계] 이상 권한(과잉 권한) 발생 시나리오 연출", flush=True)
    print("=" * 70, flush=True)
    # 1. 관리자 토큰 획득
    login_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/auth/login',
        data=json.dumps({'username': 'admin', 'password': '1234'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    token = json.loads(urllib.request.urlopen(login_req).read().decode('utf-8'))['access_token']
    auth_headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # 2. testuser의 ID 조회 후 admin 권한으로 부당 승격
    users_req = urllib.request.Request('http://127.0.0.1:5000/api/admin/users', headers=auth_headers)
    users = json.loads(urllib.request.urlopen(users_req).read().decode('utf-8'))['users']
    testuser = next((u for u in users if u['username'] == 'testuser'), None)
    assert testuser is not None, "testuser 계정을 찾을 수 없습니다."

    print(f" -> testuser의 원래 권한: {testuser.get('role')}", flush=True)

    # 부당하게 admin 권한 부여 (과잉 권한 유발)
    grant_req = urllib.request.Request(
        f"http://127.0.0.1:5000/api/admin/users/{testuser['id']}/role",
        data=json.dumps({'role': 'admin', 'reason': '테스트용 과잉 권한 부여'}).encode('utf-8'),
        headers=auth_headers,
        method='PUT'
    )
    grant_res = json.loads(urllib.request.urlopen(grant_req).read().decode('utf-8'))
    print(f" -> [이상 상태 유발] {testuser['username']}에게 관리자(admin) 권한 부당 승격 완료!", flush=True)

    # 3. 변경 상태 확인
    me_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/auth/login',
        data=json.dumps({'username': 'testuser', 'password': '1234'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    testuser_role = json.loads(urllib.request.urlopen(me_req).read().decode('utf-8'))['role']
    print(f" -> 현재 testuser 권한: '{testuser_role}' (정책 위반 상태)", flush=True)
    assert testuser_role == 'admin', "testuser가 admin으로 승격되지 않았습니다."

    print("\n" + "=" * 70, flush=True)
    print(" [2단계] 자동 권한 탐지봇 실행 (Graylog 신고 + n8n 워크플로우 트리거)", flush=True)
    print("=" * 70, flush=True)
    bot_proc = subprocess.run(
        [sys.executable, '-u', 'privilege_revoke_bot.py'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(bot_proc.stdout, flush=True)
    if bot_proc.stderr:
        print("[Bot Stderr]:", bot_proc.stderr, flush=True)

    print("\n" + "=" * 70, flush=True)
    print(" [3단계] n8n 비동기 파이프라인 처리 대기 (3초)...", flush=True)
    print("=" * 70, flush=True)
    time.sleep(3)

    print("\n" + "=" * 70, flush=True)
    print(" [4단계] 자동 회수 결과 검증 (게시판 DB & 사용자 권한 확인)", flush=True)
    print("=" * 70, flush=True)
    # testuser의 현재 권한 다시 확인
    me_req2 = urllib.request.Request(
        'http://127.0.0.1:5000/api/auth/login',
        data=json.dumps({'username': 'testuser', 'password': '1234'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    revoked_role = json.loads(urllib.request.urlopen(me_req2).read().decode('utf-8'))['role']
    print(f" -> n8n 자동 회수 후 testuser 권한: '{revoked_role}'", flush=True)

    # 보안 감사 이벤트 기록 확인
    events_req = urllib.request.Request('http://127.0.0.1:5000/api/security/events?limit=3', headers=auth_headers)
    events = json.loads(urllib.request.urlopen(events_req).read().decode('utf-8'))['events']
    print(" -> 최근 등록된 감사 로그 내역:")
    for ev in events:
        print(f"     * #{ev['id']} [{ev['decision'].upper()}] {ev.get('users')} - {ev.get('reason')}", flush=True)

    assert revoked_role == 'user', f"testuser의 권한이 user로 회수되지 않았습니다! (현재: {revoked_role})"

    print("\n" + "🎉" * 25, flush=True)
    print("골드/관리자 이상권한 자동탐지 및 Graylog + n8n 연동 자동회수 100% 성공!", flush=True)
    print("🎉" * 25, flush=True)

if __name__ == '__main__':
    run()
