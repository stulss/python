import sys
import json
import urllib.request
import time

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run():
    print("=" * 65, flush=True)
    print(" [1] 관리자 로그인", flush=True)
    print("=" * 65, flush=True)
    login_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/auth/login',
        data=json.dumps({'username': 'admin', 'password': '1234'}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    token = json.loads(urllib.request.urlopen(login_req).read().decode('utf-8'))['access_token']
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    print(" -> admin 로그인 완료", flush=True)

    print("\n" + "=" * 65, flush=True)
    print(" [2] '모던커뮤니티 보안관제' 워크플로우 (OdFvNv9vWoqt7Hqg) 상태 점검", flush=True)
    print("=" * 65, flush=True)
    status_req = urllib.request.Request('http://127.0.0.1:5000/api/n8n/status', headers=headers)
    target_wf = json.loads(urllib.request.urlopen(status_req).read().decode('utf-8'))['target_workflow']
    print(f" -> 대상 워크플로우: {target_wf['name']} (ID: {target_wf['id']})", flush=True)
    print(f" -> 활성 상태 (Active): {target_wf['active']}", flush=True)
    assert target_wf['active'] is True, "워크플로우가 비활성 상태입니다!"

    print("\n" + "=" * 65, flush=True)
    print(" [3] 침입 거부 시나리오 테스트 (Level 12 -> n8n 'deny' 판정)", flush=True)
    print("=" * 65, flush=True)
    deny_ip = "198.51.100.77"
    deny_payload = {
        'student': '모던보안팀_자동화검증',
        'alerts': [
            {
                'ip': deny_ip,
                'level': 12,
                'rule': 'RULE_SQLI_ATTACK_9901'
            }
        ]
    }
    deny_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/n8n/trigger',
        data=json.dumps(deny_payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    deny_res = urllib.request.urlopen(deny_req)
    print(f" -> n8n 웹훅 응답 상태: {deny_res.getcode()}", flush=True)
    time.sleep(2)  # n8n 비동기 파이프라인 대기

    print("\n" + "=" * 65, flush=True)
    print(" [4] 정상 허용 시나리오 테스트 (Level 5 -> n8n 'allow' 판정)", flush=True)
    print("=" * 65, flush=True)
    allow_ip = "198.51.100.88"
    allow_payload = {
        'student': '모던보안팀_자동화검증',
        'alerts': [
            {
                'ip': allow_ip,
                'level': 5,
                'rule': 'RULE_NORMAL_AUTH_1002'
            }
        ]
    }
    allow_req = urllib.request.Request(
        'http://127.0.0.1:5000/api/n8n/trigger',
        data=json.dumps(allow_payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    allow_res = urllib.request.urlopen(allow_req)
    print(f" -> n8n 웹훅 응답 상태: {allow_res.getcode()}", flush=True)
    time.sleep(2)  # n8n 비동기 파이프라인 대기

    print("\n" + "=" * 65, flush=True)
    print(" [5] 게시판에 n8n 판정 이벤트가 자동 저장되었는지 확인", flush=True)
    print("=" * 65, flush=True)
    events_req = urllib.request.Request('http://127.0.0.1:5000/api/security/events?limit=5', headers=headers)
    events = json.loads(urllib.request.urlopen(events_req).read().decode('utf-8'))['events']
    print(f" -> 최근 수신된 보안 이벤트 {len(events)}건:")
    for ev in events[:4]:
        print(f"     * #{ev['id']} [{ev['decision'].upper()}] IP: {ev['src_ip']} (레벨: {ev['level']}, 심각도: {ev['severity']}) -> {ev['reason']}", flush=True)

    deny_found = any(e['src_ip'] == deny_ip and e['decision'] == 'deny' for e in events)
    allow_found = any(e['src_ip'] == allow_ip and e['decision'] == 'allow' for e in events)

    assert deny_found, f"거부 이벤트({deny_ip})가 게시판에 자동 저장되지 않았습니다!"
    assert allow_found, f"허용 이벤트({allow_ip})가 게시판에 자동 저장되지 않았습니다!"

    print("\n" + "🎉" * 25, flush=True)
    print("모던커뮤니티 보안관제 워크플로우 완벽 연결 및 양방향 자동화 검증 100% 성공!", flush=True)
    print("🎉" * 25, flush=True)

if __name__ == '__main__':
    run()
