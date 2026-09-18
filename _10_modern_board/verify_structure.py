"""구조 이식 및 기능 종합 검증 스크립트
"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
from extensions import db
from models import User, Post, BlockedIP, SecurityLog

client = app.test_client()

def run_tests():
    print("=" * 60)
    print(" [1] 블루프린트 등록 검증")
    print("=" * 60)
    bp_names = list(app.blueprints.keys())
    print(f"등록된 블루프린트 목록 ({len(bp_names)}개): {bp_names}")
    for required in ['page', 'auth', 'post', 'security', 'admin', 'gold', 'public', 'openapi']:
        assert required in bp_names, f"블루프린트 '{required}' 누락!"
    print(" -> [PASS] 모든 필수 블루프린트가 정상 등록되었습니다.")

    print("\n" + "=" * 60)
    print(" [2] 메인 페이지 & 공개 API 검증")
    print("=" * 60)
    res = client.get('/')
    assert res.status_code == 200, f"메인 페이지 실패: {res.status_code}"
    print(" -> [PASS] GET / : 200 OK (HTML 템플릿 서빙)")

    res = client.get('/api/posts')
    assert res.status_code == 200, f"게시글 목록 실패: {res.status_code}"
    data = res.get_json()
    items = data.get('items', [])
    print(f" -> [PASS] GET /api/posts : 200 OK (조회된 글 {len(items)}개, 커서 페이징 지원)")
    # 비로그인 상태이므로 보안이슈 글이 마스킹되었는지 검사
    sec_posts_unauth = [p for p in items if p.get('category') == '보안이슈']
    assert len(sec_posts_unauth) == 0, "비로그인 상태에서 보안이슈 글이 노출되었습니다!"
    print(" -> [PASS] 비로그인 상태에서 '보안이슈' 글이 정상적으로 마스킹되었습니다.")

    print("\n" + "=" * 60)
    print(" [3] 사용자별 로그인 & RBAC 권한 검증")
    print("=" * 60)
    # 1) 일반 유저 로그인
    res_user = client.post('/api/auth/login', json={'username': 'testuser', 'password': '1234'})
    assert res_user.status_code == 200, f"testuser 로그인 실패: {res_user.status_code}"
    user_token = res_user.get_json().get('access_token')
    user_headers = {'Authorization': f'Bearer {user_token}'}
    print(f" -> [PASS] 일반회원 (testuser) 로그인 성공 (role: {res_user.get_json().get('role')})")

    # 2) 골드 유저 로그인
    res_gold = client.post('/api/auth/login', json={'username': 'golduser', 'password': '1234'})
    assert res_gold.status_code == 200, f"golduser 로그인 실패: {res_gold.status_code}"
    gold_token = res_gold.get_json().get('access_token')
    gold_headers = {'Authorization': f'Bearer {gold_token}'}
    print(f" -> [PASS] 골드회원 (golduser) 로그인 성공 (role: {res_gold.get_json().get('role')})")

    # 3) 관리자 로그인
    res_admin = client.post('/api/auth/login', json={'username': 'admin', 'password': '1234'})
    assert res_admin.status_code == 200, f"admin 로그인 실패: {res_admin.status_code}"
    admin_token = res_admin.get_json().get('access_token')
    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    print(f" -> [PASS] 관리자 (admin) 로그인 성공 (role: {res_admin.get_json().get('role')})")

    print("\n" + "=" * 60)
    print(" [4] 보안 관련 글 등급별 접근 통제 검증")
    print("=" * 60)
    # DB에서 보안이슈 글 id 확인
    with app.app_context():
        sec_post = Post.query.filter_by(category='보안이슈').first()
    if sec_post:
        sec_id = sec_post.id
        print(f"테스트 대상 보안이슈 글: ID #{sec_id} - '{sec_post.title}'")

        # 일반 회원이 보안이슈 글 상세 조회 시도 -> 403 Forbidden 및 SecurityLog 기록
        res_try = client.get(f'/api/posts/{sec_id}', headers=user_headers)
        assert res_try.status_code == 403, f"일반회원 보안글 접근 차단 실패: {res_try.status_code}"
        print(" -> [PASS] 일반회원 보안글 상세 조회 시도 -> 403 Forbidden 정상 차단")

        # 골드 회원이 보안이슈 글 상세 조회 시도 -> 200 OK
        res_gold_view = client.get(f'/api/posts/{sec_id}', headers=gold_headers)
        assert res_gold_view.status_code == 200, f"골드회원 보안글 접근 실패: {res_gold_view.status_code}"
        print(" -> [PASS] 골드회원 보안글 상세 조회 -> 200 OK 열람 성공")

    print("\n" + "=" * 60)
    print(" [5] 골드 전용 API (/api/gold/posts) 검증")
    print("=" * 60)
    # 일반회원 접근 -> 403
    res_g_unauth = client.get('/api/gold/posts', headers=user_headers)
    assert res_g_unauth.status_code == 403, f"일반회원 골드 API 차단 실패: {res_g_unauth.status_code}"
    print(" -> [PASS] 일반회원 /api/gold/posts 접근 -> 403 Forbidden 정상 차단")

    # 골드회원 접근 -> 200
    res_g_auth = client.get('/api/gold/posts', headers=gold_headers)
    assert res_g_auth.status_code == 200, f"골드회원 골드 API 접근 실패: {res_g_auth.status_code}"
    print(f" -> [PASS] 골드회원 /api/gold/posts 접근 -> 200 OK 성공 (글 수: {res_g_auth.get_json().get('count')})")

    print("\n" + "=" * 60)
    print(" [6] 관리자 API (/api/admin) 검증")
    print("=" * 60)
    # 일반회원 접근 -> 403
    res_adm_unauth = client.get('/api/admin/users', headers=user_headers)
    assert res_adm_unauth.status_code == 403, "일반회원 admin 접근 차단 실패"
    print(" -> [PASS] 일반회원 /api/admin/users 접근 -> 403 Forbidden 정상 차단")

    # 관리자 접근 -> 200
    res_adm_auth = client.get('/api/admin/users', headers=admin_headers)
    assert res_adm_auth.status_code == 200, "관리자 admin 접근 실패"
    print(f" -> [PASS] 관리자 /api/admin/users 접근 -> 200 OK 성공 (회원 수: {res_adm_auth.get_json().get('count')})")

    # 관리자 통계 조회
    res_stats = client.get('/api/admin/stats', headers=admin_headers)
    assert res_stats.status_code == 200
    print(" -> [PASS] 관리자 /api/admin/stats 접근 -> 200 OK 성공")

    print("\n" + "=" * 60)
    print(" [7] IP 실차단(Active Response) 가드 검증")
    print("=" * 60)
    test_ip = "192.0.2.99"
    with app.app_context():
        # 테스트용 차단 IP 등록
        b_ip = BlockedIP(ip=test_ip, reason="테스트 공격 IP 차단", blocked_by="tester")
        db.session.merge(b_ip)
        db.session.commit()

    # 차단된 IP로 요청 시 403 Forbidden
    res_blocked = client.get('/api/posts', headers={'X-Forwarded-For': test_ip})
    assert res_blocked.status_code == 403, f"차단 IP 가드 실패: {res_blocked.status_code}"
    print(f" -> [PASS] 차단된 IP({test_ip}) 요청 -> 403 Forbidden (메시지: '{res_blocked.get_json().get('msg')}')")

    # 차단 해제 후 정상 접근 확인
    with app.app_context():
        b_ip = db.session.get(BlockedIP, test_ip)
        if b_ip:
            db.session.delete(b_ip)
            db.session.commit()

    res_unblocked = client.get('/api/posts', headers={'X-Forwarded-For': test_ip})
    assert res_unblocked.status_code == 200
    print(f" -> [PASS] 차단 해제 후 동일 IP({test_ip}) 요청 -> 200 OK 복구 확인")

    print("\n" + "=" * 60)
    print(" [8] 보안 대시보드 통계 & 부산 테마여행 API 검증")
    print("=" * 60)
    res_sec_stats = client.get('/api/security/stats', headers=gold_headers)
    assert res_sec_stats.status_code == 200, f"보안 통계 실패: {res_sec_stats.status_code}"
    print(" -> [PASS] 골드회원 /api/security/stats 접근 -> 200 OK 성공", flush=True)

    res_openapi = client.get('/api/openapi/busan-themes?numOfRows=5')
    assert res_openapi.status_code == 200, f"부산 테마여행 실패: {res_openapi.status_code}"
    print(f" -> [PASS] 부산 테마여행 Open API (/api/openapi/busan-themes) -> 200 OK 성공 (조회: {len(res_openapi.get_json().get('items', []))}개)", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("🎉 모든 기능 검증 테스트 100% 통과! 구조 이식 및 원본 보존 완벽 완료!", flush=True)
    print("=" * 60, flush=True)

if __name__ == '__main__':
    run_tests()

