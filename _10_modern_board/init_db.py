import os
import sys
import pymysql
from urllib.parse import urlparse

# Windows cp949 터미널 인코딩 호환성 보장
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import create_app
from extensions import db
from models import User, Post, Comment, SecurityLog, SecurityEvent
from datetime import datetime, timedelta


def ensure_database_exists():
    """DATABASE_URL의 데이터베이스가 없으면 자동 생성"""
    db_url = os.getenv('DATABASE_URL', 'mysql+pymysql://root:123456@localhost:3306/modern_board_db')
    if db_url.startswith('mysql+pymysql://'):
        parsed = urlparse(db_url)
        db_name = parsed.path.lstrip('/')
        host = parsed.hostname or 'localhost'
        port = parsed.port or 3306
        user = parsed.username or 'root'
        password = parsed.password or ''

        try:
            conn = pymysql.connect(host=host, port=port, user=user, password=password)
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            conn.close()
            print(f"[OK] MySQL Database `{db_name}` checked/created.")
        except Exception as e:
            print(f"[WARN] MySQL database auto-create skipped: {e}")



def seed_data():
    app = create_app()
    with app.app_context():
        # 테이블 생성
        print("[*] Creating database tables...")
        db.create_all()

        # users 테이블에 nickname 컬럼 추가 (없을 경우)
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE users ADD COLUMN nickname VARCHAR(50) NULL;"))
                conn.commit()
        except Exception:
            pass  # 이미 존재함

        # 기존 사용자 확인 및 동기화
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            admin_user.set_password('1234')
            admin_user.nickname = '관리자'
            
            # golduser 확인 및 생성/동기화
            gold_user = User.query.filter_by(username='golduser').first()
            if not gold_user:
                gold_user = User(username='golduser', nickname='골드회원', email='gold@aleph.io', role='gold')
                gold_user.set_password('1234')
                db.session.add(gold_user)
            else:
                gold_user.role = 'gold'
                gold_user.nickname = '골드회원'
                gold_user.set_password('1234')
            
            # testuser 확인 및 비밀번호 동기화
            test_user = User.query.filter_by(username='testuser').first()
            if test_user:
                test_user.set_password('1234')
                test_user.nickname = test_user.nickname or '홍길동'

            db.session.commit()
            print("[INFO] Database already initialized. Admin/Gold/Test users verified & synced.")
            return

        print("[*] Seeding sample data...")

        # 1. 사용자 생성 (_7_ 백업 스펙의 admin/1234, testuser/1234, golduser/1234 포함)
        users = [
            User(username='admin', nickname='관리자', email='admin@sec-corp.io', role='admin'),
            User(username='golduser', nickname='골드회원', email='gold@aleph.io', role='gold'),
            User(username='testuser', nickname='홍길동', email='testuser@aleph.io', role='user'),
            User(username='alice', nickname='앨리스', email='alice@dev.io', role='user'),
            User(username='bob', nickname='밥', email='bob@security.io', role='user'),
            User(username='charlie', nickname='찰리', email='charlie@frontend.io', role='user'),
            User(username='soarbot', nickname='보안봇', email='soarbot@security.internal', role='admin')
        ]
        for u in users:
            u.set_password('1234')

        db.session.add_all(users)
        db.session.commit()


        # 2. 게시글 샘플 생성 (커서 기반 페이징 테스트를 위한 16개 데이터)
        posts_data = [
            {
                'title': '📢 [공지] 모던 시큐리티 게시판 오픈 안내 및 이용 수칙',
                'content': '반갑습니다! Tailwind CSS와 JWT, 커서 기반 페이징으로 제작된 차세대 모던 게시판입니다.\n\n안전하고 쾌적한 커뮤니티 이용을 위해 타인을 비방하거나 악성 스크립트를 삽입하는 행위는 엄격히 금지되며 보안 관제 시스템에 의해 실시간 로깅됩니다.',
                'category': '공지사항',
                'tags': '공지,시스템,보안',
                'author': users[0],
                'is_pinned': True,
                'views': 342,
                'likes': 45
            },
            {
                'title': '🛡️ [보안 가이드] JWT 토큰 안전하게 다루는 실무 모범사례',
                'content': 'JWT(JSON Web Token)는 무상태 인증에 매우 유용하지만, XSS와 CSRF 공격에 대한 대비가 필수입니다.\n\n1. 민감한 정보(비밀번호, 개인정보)는 토큰 Payload에 절대 담지 마세요.\n2. Access Token의 유효기간은 짧게(15~60분) 설정하고, Refresh Token Rotation(RTR)을 도입하세요.\n3. 클라이언트 저장소는 HTTP-Only Cookie 또는 안전한 Storage 정책을 수립해야 합니다.',
                'category': '보안이슈',
                'tags': 'JWT,웹보안,보안수칙',
                'author': users[2],
                'is_pinned': False,
                'views': 189,
                'likes': 28
            },
            {
                'title': '⚡ 커서 기반 페이징(Cursor-based Pagination)이 왜 빠른가?',
                'content': '전통적인 오프셋 기반 페이징(OFFSET 100000 LIMIT 10)은 데이터베이스가 앞선 10만 개 레코드를 모두 읽고 버려야 하므로 데이터가 커질수록 극심한 병목이 발생합니다.\n\n반면 커서 기반 페이징은 WHERE id < :last_seen_id ORDER BY id DESC LIMIT 10 과 같이 B-Tree 인덱스를 직접 탐색하므로 데이터가 수천만 건이어도 O(1) 수준의 일정한 고속 조회가 보장됩니다!',
                'category': '기술Q&A',
                'tags': 'Database,MySQL,성능최적화',
                'author': users[1],
                'is_pinned': False,
                'views': 250,
                'likes': 37
            },
            {
                'title': '🎨 Tailwind CSS와 Shadcn UI로 감각적인 대시보드 구축하기',
                'content': '최근 웹 프론트엔드 트렌드는 유틸리티 우선(Utility-first) CSS 프레임워크인 Tailwind를 기반으로, 일관된 디자인 토큰과 컴포넌트 접근성을 제공하는 Shadcn UI 스타일이 대세입니다.\n\n다크 모드와 슬레이트 컬러 팔레트, 절제된 글래스모피즘이 결합되면 뛰어난 심미성을 자랑합니다.',
                'category': '팁&노하우',
                'tags': 'TailwindCSS,UI/UX,프론트엔드',
                'author': users[3],
                'is_pinned': False,
                'views': 120,
                'likes': 19
            },
            {
                'title': '🐳 도커 데스크탑 환경에서 Flask + MySQL 연동 꿀팁',
                'content': 'Docker 컨테이너로 MySQL을 구동할 때는 포트 포워딩(-p 3306:3306)과 볼륨 마운트를 반드시 체크해야 합니다.\n또한 Flask의 SQLAlchemy 연결 문자열에서는 utf8mb4 인코딩을 지정해 한글 및 이모지 깨짐을 방지할 수 있습니다.',
                'category': '기술Q&A',
                'tags': 'Docker,Flask,MySQL',
                'author': users[4],
                'is_pinned': False,
                'views': 95,
                'likes': 12
            },
            {
                'title': '☕ 주말에 읽기 좋은 개발 및 사이버 보안 추천 도서 리스트',
                'content': '1. 화이트 해커를 위한 웹 해킹의 기술\n2. Real MySQL 8.0\n3. 클린 아키텍처\n4. 모던 자바스크립트 Deep Dive\n다들 이번 주말에 어떤 책 읽으실 계획인가요?',
                'category': '자유게시판',
                'tags': '도서추천,주말,스터디',
                'author': users[1],
                'is_pinned': False,
                'views': 78,
                'likes': 9
            },
            {
                'title': '⚠️ [경보] 최근 급증하는 SQL Injection 및 Credential Stuffing 공격 동향',
                'content': '자동화된 스크립트를 이용한 무차별 대입(Brute-force) 공격과 쿼리 파라미터 조작 시도가 감지되고 있습니다.\n\nPrepared Statement를 상시 적용하고 비정상적인 요청 빈도는 IP 기반 Rate Limiting으로 즉시 차단해야 합니다.',
                'category': '보안이슈',
                'tags': '보안관제,SQLi,대응체계',
                'author': users[0],
                'is_pinned': False,
                'views': 310,
                'likes': 41
            },
            {
                'title': '💡 Flask 3.0에서 Blueprint와 Application Factory 패턴 적용기',
                'content': '단일 파일로 시작했던 Flask 앱이 거대해질 때는 Blueprint를 적극 활용해 도메인별(인증, 게시판, 관리자, 보안)로 분리하는 것이 유지보수에 핵심적입니다.',
                'category': '기술Q&A',
                'tags': 'Python,Flask,클린코드',
                'author': users[1],
                'is_pinned': False,
                'views': 64,
                'likes': 8
            },
            {
                'title': '🚀 RESTful API 응답 규격과 일관된 에러 처리 설계',
                'content': '성공 응답과 에러 응답의 JSON 스키마가 일관되어야 프론트엔드 연동 시 예외 처리가 매끄러워집니다. 상태 코드(200, 201, 400, 401, 403, 404, 500)를 엄격히 준수합시다.',
                'category': '팁&노하우',
                'tags': 'API,RESTful,아키텍처',
                'author': users[3],
                'is_pinned': False,
                'views': 82,
                'likes': 14
            },
            {
                'title': '🎉 새 프로젝트 개설 축하드립니다!',
                'content': '연습용 게시판 인터페이스가 정말 세련되고 깔끔하네요! 반응형 모바일에서도 아주 부드럽게 잘 작동합니다.',
                'category': '자유게시판',
                'tags': '응원,자유,소통',
                'author': users[4],
                'is_pinned': False,
                'views': 45,
                'likes': 7
            },
            {
                'title': '🔍 검색 엔진 인덱싱과 MySQL Full-Text Search 도입 방안',
                'content': 'LIKE %keyword% 방식은 테이블 풀스캔이 일어나므로 대용량 데이터 환경에서는 ngram 파서 기반의 Full-Text 인덱스를 고려하는 것이 좋습니다.',
                'category': '기술Q&A',
                'tags': 'MySQL,검색,인덱스',
                'author': users[2],
                'is_pinned': False,
                'views': 110,
                'likes': 15
            },
            {
                'title': '🔐 관리자 권한 분리와 RBAC(역할 기반 접근 제어) 설계',
                'content': '일반 사용자와 관리자를 철저히 분리하고 민감한 변경 작업에는 2차 검증과 감사 로그 기록이 수반되어야 합니다.',
                'category': '보안이슈',
                'tags': 'RBAC,보안감사,인가',
                'author': users[0],
                'is_pinned': False,
                'views': 135,
                'likes': 22
            }
        ]

        created_posts = []
        base_time = datetime.utcnow() - timedelta(days=5)

        for i, p_info in enumerate(posts_data):
            post_time = base_time + timedelta(hours=i * 7, minutes=i * 12)
            post = Post(
                title=p_info['title'],
                content=p_info['content'],
                category=p_info['category'],
                tags=p_info['tags'],
                is_pinned=p_info['is_pinned'],
                view_count=p_info['views'],
                like_count=p_info['likes'],
                author_id=p_info['author'].id,
                author_name=p_info['author'].username,
                created_at=post_time,
                updated_at=post_time
            )
            db.session.add(post)
            created_posts.append(post)

        db.session.commit()

        # 3. 댓글 샘플 생성
        sample_comments = [
            Comment(post_id=created_posts[0].id, author_id=users[1].id, author_name='alice', content='공지 확인했습니다! 유용한 기능이 많네요.'),
            Comment(post_id=created_posts[0].id, author_id=users[2].id, author_name='bob', content='보안 대시보드 실시간 연동이 특히 기대됩니다.'),
            Comment(post_id=created_posts[1].id, author_id=users[3].id, author_name='charlie', content='RTR(Refresh Token Rotation) 개념 설명 감사합니다.'),
            Comment(post_id=created_posts[2].id, author_id=users[4].id, author_name='dave', content='커서 페이징 직접 구현해보니 확실히 offset보다 빠르네요!'),
            Comment(post_id=created_posts[3].id, author_id=users[1].id, author_name='alice', content='Tailwind 색상 팔레트 추천 부탁드립니다!')
        ]
        db.session.add_all(sample_comments)

        # 4. 초기 보안 감사 로그 샘플 주입
        now = datetime.utcnow()
        sample_logs = [
            SecurityLog(
                event_type='LOGIN_SUCCESS',
                severity='INFO',
                ip_address='127.0.0.1',
                endpoint='/api/auth/login',
                method='POST',
                status_code=200,
                user_id=users[0].id,
                username='admin',
                details='Administrator login successful from localhost session',
                created_at=now - timedelta(hours=2)
            ),
            SecurityLog(
                event_type='LOGIN_FAIL',
                severity='WARNING',
                ip_address='203.0.113.42',
                endpoint='/api/auth/login',
                method='POST',
                status_code=401,
                username='root',
                details='Failed login attempt for unknown user "root"',
                created_at=now - timedelta(hours=5)
            ),
            SecurityLog(
                event_type='SQLI_DETECT',
                severity='CRITICAL',
                ip_address='198.51.100.12',
                endpoint='/api/posts?search=1%20OR%201=1',
                method='GET',
                status_code=400,
                username='anonymous',
                details='Pattern match: SQL Injection syntax "OR 1=1" intercepted in query parameter',
                created_at=now - timedelta(hours=8)
            ),
            SecurityLog(
                event_type='UNAUTHORIZED_ACCESS',
                severity='WARNING',
                ip_address='192.168.1.150',
                endpoint='/api/admin/users',
                method='GET',
                status_code=401,
                username='guest',
                details='Attempted to query administrative endpoints without authorization token',
                created_at=now - timedelta(hours=14)
            ),
            SecurityLog(
                event_type='BRUTE_FORCE',
                severity='HIGH',
                ip_address='185.220.101.5',
                endpoint='/api/auth/login',
                method='POST',
                status_code=429,
                username='admin',
                details='High volume login failure rate detected: 22 attempts in 30 seconds',
                created_at=now - timedelta(days=1, hours=3)
            ),
            SecurityLog(
                event_type='USER_REGISTER',
                severity='INFO',
                ip_address='127.0.0.1',
                endpoint='/api/auth/register',
                method='POST',
                status_code=201,
                user_id=users[1].id,
                username='alice',
                details='New regular user registration completed',
                created_at=now - timedelta(days=2)
            )
        ]
        db.session.add_all(sample_logs)

        # 5. _7_ 백업 스펙: n8n SOAR 보안 이벤트 샘플 주입
        sample_events = [
            SecurityEvent(
                student='student_01',
                src_ip='192.168.1.55',
                level=3,
                rule='SSH_BRUTE_FORCE',
                rule_id='RULE_AUTH_01',
                fail_count=8,
                decision='deny',
                severity='High',
                reason='n8n 자동화 판정: 60초 내 연속 로그인 실패 임계치 초과로 접근 차단',
                generated_at=(now - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            ),
            SecurityEvent(
                student='student_02',
                src_ip='10.0.0.12',
                level=1,
                rule='NORMAL_TRAFFIC',
                rule_id='RULE_ALLOW_01',
                fail_count=0,
                decision='allow',
                severity='Low',
                reason='정상 인가된 세션 접속 허용',
                generated_at=(now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            )
        ]
        db.session.add_all(sample_events)

        db.session.commit()
        print("[SUCCESS] All sample data (_7_ backup compatible: admin/testuser/soarbot, security_events) successfully seeded!")



if __name__ == '__main__':
    ensure_database_exists()
    seed_data()

