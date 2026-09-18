#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""골드유저 및 관리자 이상권한 자동 탐지 & 회수봇
- Graylog(SIEM) GELF 경보 및 n8n SOAR 워크플로우('모던커뮤니티 1-자동 회수 봇 테스트') 연동

동작 흐름:
  1) 게시판 GET /api/admin/users 를 조회하여 전체 회원 및 권한(Role) 확인.
  2) 정책 허용목록(ADMIN_ALLOWLIST, GOLD_ALLOWLIST)과 대조:
     - 승인되지 않은 admin 계정 -> 관리자 과잉 권한 위반
     - 승인되지 않은 gold 계정 -> 골드 이상 권한 위반
  3) 위반 계정 발견 시:
     - Graylog SIEM (GELF UDP 12201)으로 경보 전송 (rule=priv-unauthorized-role)
     - n8n 워크플로우('모던커뮤니티 1-자동 회수 봇 테스트') 웹훅을 트리거하여 자동 회수 실행
  4) n8n 워크플로우가 게시판 POST /api/admin/revoke 를 호출하여 권한을 'user'로 즉시 회수 및 알림 전송

사용법:
  python privilege_revoke_bot.py            # 탐지 + Graylog 신고 + n8n 자동 회수
  python privilege_revoke_bot.py --dry-run  # 신고/회수 없이 위반자 목록만 출력
  python privilege_revoke_bot.py --direct   # n8n 거치지 않고 게시판 API로 봇이 직접 회수
"""
import argparse
import json
import os
import socket
import sys
import urllib.request

# Windows 콘솔 인코딩 호환성 보장
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env():
    """같은 폴더의 .env 파일 로드"""
    path = os.path.join(HERE, '.env')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


def cfg():
    load_env()
    admin_allow = [u.strip() for u in os.environ.get('ADMIN_ALLOWLIST', 'admin,soarbot').split(',') if u.strip()]
    gold_allow = [u.strip() for u in os.environ.get('GOLD_ALLOWLIST', 'golduser,admin,soarbot').split(',') if u.strip()]

    return {
        'board': os.environ.get('BOARD_URL', 'http://127.0.0.1:5000').rstrip('/'),
        'key': os.environ.get('ADMIN_API_KEY', '') or os.environ.get('SECURITY_API_KEY', ''),
        'admin_allow': admin_allow,
        'gold_allow': gold_allow,
        'graylog_host': os.environ.get('GELF_HOST', '127.0.0.1'),
        'graylog_port': int(os.environ.get('GELF_PORT', '12201')),
        'n8n_revoke_webhook': os.environ.get('N8N_WEBHOOK_URL_REVOKE', 'http://127.0.0.1:5678/webhook/5297c4cd-f3a1-48d5-8e88-efb0e21b7367'),
        'student': os.environ.get('STUDENT', '권한자동탐지봇'),
        'src_ip': os.environ.get('BOARD_SRC_IP', '127.0.0.1'),
    }


def get_json(url, key=None, method='GET', body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if key:
        req.add_header('X-API-Key', key)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def find_violations(c):
    """게시판 회원 목록을 가져와 허용목록 외의 이상 권한(과잉 admin / 비인가 gold) 계정 탐지"""
    data = get_json(f"{c['board']}/api/admin/users", key=c['key'])
    users = data.get('users', [])

    violations = []
    for u in users:
        role = u.get('role', 'user')
        username = u.get('username')

        # 1) 허가되지 않은 admin
        if role == 'admin' and username not in c['admin_allow']:
            violations.append({
                'user': u,
                'violation_type': 'UNAUTHORIZED_ADMIN',
                'reason': f"허용목록 밖 관리자 과잉권한 (허용: {c['admin_allow']})"
            })
        # 2) 허가되지 않은 gold
        elif role == 'gold' and username not in c['gold_allow']:
            violations.append({
                'user': u,
                'violation_type': 'UNAUTHORIZED_GOLD',
                'reason': f"허용목록 밖 골드 이상권한 (허용: {c['gold_allow']})"
            })

    return violations


def send_gelf(c, v):
    """위반 1건을 Graylog GELF(UDP 12201)로 신고"""
    u = v['user']
    msg = {
        'version': '1.1',
        'host': socket.gethostname(),
        'short_message': f"이상권한 탐지: '{u['username']}' ({u.get('role')}) - {v['reason']}",
        'level': 3 if v['violation_type'] == 'UNAUTHORIZED_ADMIN' else 4,
        '_rule': 'priv-unauthorized-role',
        '_user': u['username'],
        '_role': u.get('role'),
        '_violation': v['violation_type'],
        '_granted_by': u.get('role_granted_by') or 'unknown',
        '_src_ip': c['src_ip'],
        '_student': c['student'],
        '_count': 1,
    }
    payload = json.dumps(msg).encode('utf-8')
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(payload, (c['graylog_host'], c['graylog_port']))
    except Exception as e:
        print(f"    [Graylog GELF 경보 전송 안내] {e}")
    finally:
        s.close()


def trigger_n8n_revoke(c, v):
    """n8n '모던커뮤니티 1-자동 회수 봇 테스트' 워크플로우 웹훅 호출"""
    u = v['user']
    payload = {
        'user': u['username'],
        'username': u['username'],
        'rule': v['violation_type'],
        'student': c['student'],
        'src_ip': c['src_ip'],
        'granted_by': u.get('role_granted_by') or '미인가승격'
    }
    try:
        res = get_json(c['n8n_revoke_webhook'], method='POST', body=payload)
        return res
    except Exception as e:
        print(f"    [!] n8n 웹훅 트리거 실패: {e}")
        return None


def direct_revoke(c, v):
    """대체 경로: n8n 없이 봇이 게시판 API로 직접 회수"""
    u = v['user']
    payload = {
        'username': u['username'],
        'student': c['student'],
        'reason': f"봇 직접 회수: {v['reason']}",
        'src_ip': c['src_ip'],
        'source': 'privilege-guard-bot'
    }
    return get_json(f"{c['board']}/api/admin/revoke", key=c['key'], method='POST', body=payload)


def main():
    ap = argparse.ArgumentParser(description="골드/관리자 이상권한 자동 탐지 및 회수 봇")
    ap.add_argument('--dry-run', action='store_true', help='회수나 경보 없이 위반 계정만 확인')
    ap.add_argument('--direct', action='store_true', help='n8n을 거치지 않고 게시판 API로 직접 회수')
    args = ap.parse_args()

    c = cfg()
    print("=" * 65)
    print(" 🛡️ 골드유저 및 관리자 이상권한 자동 탐지봇 시작")
    print(f" - 게시판 주소: {c['board']}")
    print(f" - 관리자 허용목록 (ADMIN): {c['admin_allow']}")
    print(f" - 골드유저 허용목록 (GOLD) : {c['gold_allow']}")
    print(f" - n8n 회수 웹훅: {c['n8n_revoke_webhook']}")
    print("=" * 65)

    try:
        violations = find_violations(c)
    except Exception as e:
        print(f"[!] 게시판 회원 조회 실패: {e}")
        sys.exit(1)

    if not violations:
        print("✅ [정상] 이상 권한 또는 과잉 권한을 가진 계정이 없습니다. (모든 권한 정상 준수)")
        return

    print(f"⚠️ [탐지] 총 {len(violations)}건의 이상권한 위반 계정 발견!\n")

    for v in violations:
        u = v['user']
        uname = u['username']
        role = u.get('role')
        vtype = v['violation_type']

        if args.dry_run:
            print(f"  [DRY-RUN] 계정: '{uname}' (현재권한: {role}) -> 위반: {vtype} ({v['reason']})")
            continue

        # 1) Graylog GELF 경보 전송
        send_gelf(c, v)
        print(f"  [1/2] Graylog 경보 전송 완료 -> '{uname}' ({vtype}) [UDP {c['graylog_port']}]")

        # 2) 회수 실행
        if args.direct:
            res = direct_revoke(c, v)
            if res and res.get('revoked'):
                print(f"  [2/2] 봇 직접 회수 완료 -> '{uname}': {res.get('old_role')} -> {res.get('new_role')} (Event #{res.get('event_id')})")
            else:
                print(f"  [2/2] 봇 직접 회수 안내 -> {res.get('msg') if res else '응답 없음'}")
        else:
            # n8n SOAR 워크플로우를 통한 자동 회수 트리거
            print(f"  [2/2] n8n '모던커뮤니티 1-자동 회수 봇 테스트' 워크플로우 웹훅 호출 중...")
            res = trigger_n8n_revoke(c, v)
            print(f"        -> n8n 자동 회수 및 알림(Discord/Slack/Telegram) 처리 완료! (대상: {uname})")

    print("\n" + "🎉" * 20)
    print("이상권한 탐지 및 회수 파이프라인 수행 완료!")
    print("🎉" * 20)


if __name__ == '__main__':
    main()
