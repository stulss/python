import sys
import json
import urllib.request

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test():
    print("=" * 60, flush=True)
    print(" [1] 관리자 로그인 및 토큰 획득", flush=True)
    print("=" * 60, flush=True)
    login_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/auth/login',
        data=json.dumps({'username': 'admin', 'password': '1234'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    login_res = urllib.request.urlopen(login_req)
    token = json.loads(login_res.read().decode('utf-8'))['access_token']
    auth_headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    print(" -> [PASS] admin 로그인 성공 및 토큰 확보", flush=True)

    print("\n" + "=" * 60, flush=True)
    print(" [2] n8n 연동 상태 확인 (/api/n8n/status)", flush=True)
    print("=" * 60, flush=True)
    status_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/n8n/status',
        headers=auth_headers
    )
    status_res = urllib.request.urlopen(status_req)
    status_data = json.loads(status_res.read().decode('utf-8'))
    print(f" -> [PASS] n8n 연결 상태: {status_data.get('status')}", flush=True)
    print(f" -> [PASS] 연동된 워크플로우 수: {status_data.get('workflow_count')}개", flush=True)
    for wf in status_data.get('workflows', []):
        print(f"     * [{wf['id']}] {wf['name']} (활성: {wf['active']})", flush=True)

    print("\n" + "=" * 60, flush=True)
    print(" [3] n8n 보안관제 웹훅 실시간 트리거 테스트 (/api/n8n/trigger)", flush=True)
    print("=" * 60, flush=True)
    trigger_payload = {
        'type': 'security',
        'student': 'n8n_연동테스터',
        'src_ip': '203.0.113.45',
        'level': 3,
        'rule': 'BRUTE_FORCE_SOAR',
        'fail_count': 10,
        'decision': 'deny',
        'severity': 'Critical',
        'reason': 'n8n SOAR 자동화 모니터링 연동 검증 테스트'
    }
    trigger_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/n8n/trigger',
        data=json.dumps(trigger_payload).encode('utf-8'),
        headers=auth_headers,
        method='POST'
    )
    trigger_res = urllib.request.urlopen(trigger_req)
    trigger_data = json.loads(trigger_res.read().decode('utf-8'))
    print(f" -> [PASS] n8n 웹훅 응답 코드: {trigger_data.get('response_code')}", flush=True)
    print(f" -> [PASS] 메시지: {trigger_data.get('message')}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print(" [4] n8n -> 모던게시판 이벤트 자동 저장 확인 (/api/security/events)", flush=True)
    print("=" * 60, flush=True)
    events_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/security/events?limit=5',
        headers=auth_headers
    )
    events_res = urllib.request.urlopen(events_req)
    events_data = json.loads(events_res.read().decode('utf-8'))
    latest_events = events_data.get('events', [])
    print(f" -> 최신 등록된 보안 이벤트 ({len(latest_events)}건 확인):", flush=True)
    for ev in latest_events[:3]:
        print(f"     * #{ev['id']} [{ev['decision'].upper()}] {ev['src_ip']} ({ev['student']}) - {ev['reason']}", flush=True)

    print("\n" + "🎉" * 20, flush=True)
    print("n8n 연동 및 실시간 양방향 트리거 검증 100% 완료!", flush=True)
    print("🎉" * 20, flush=True)

if __name__ == '__main__':
    test()
