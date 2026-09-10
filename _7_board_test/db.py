import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash
from config import Config


def get_db_connection():
  """데이터베이스 커넥션 생성 (DictCursor)"""
  return pymysql.connect(
      host=Config.DB_HOST,
      port=Config.DB_PORT,
      user=Config.DB_USER,
      password=Config.DB_PASSWORD,
      database=Config.DB_NAME,
      charset="utf8mb4",
      cursorclass=pymysql.cursors.DictCursor,
      autocommit=False,
  )


def init_db():
  """데이터베이스 및 테이블 자동 생성 및 초기 데이터 주입"""
  # 1. DB 생성용 기본 연결
  conn = pymysql.connect(
      host=Config.DB_HOST,
      port=Config.DB_PORT,
      user=Config.DB_USER,
      password=Config.DB_PASSWORD,
      charset="utf8mb4",
      cursorclass=pymysql.cursors.DictCursor,
  )

  try:
    with conn.cursor() as cursor:
      # DB 생성
      cursor.execute(
          f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET"
          " utf8mb4 COLLATE utf8mb4_unicode_ci;"
      )
      cursor.execute(f"USE `{Config.DB_NAME}`;")

      # 유저 테이블 생성
      cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    nickname VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # 게시글 테이블 생성 (커서 페이징 최적화 인덱스 추가)
      cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    category VARCHAR(50) NOT NULL DEFAULT '일반',
                    views INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_id_desc (id DESC),
                    INDEX idx_category_id (category, id DESC),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # 보안 이벤트 테이블 생성 (n8n 이 판정 결과를 REST 로 저장하는 곳)
      cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student VARCHAR(50) NOT NULL,
                    src_ip VARCHAR(45) NOT NULL,
                    fail_count INT NOT NULL DEFAULT 0,
                    decision VARCHAR(10) NOT NULL,
                    severity VARCHAR(10) NOT NULL DEFAULT 'Low',
                    reason VARCHAR(200),
                    rule_id VARCHAR(50),
                    generated_at VARCHAR(32),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_student (student),
                    INDEX idx_src_ip (src_ip),
                    INDEX idx_decision (decision)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

      # 샘플 데이터 주입 (유저가 없을 때 기본 테스트 계정 및 게시글 생성)
      cursor.execute("SELECT COUNT(*) AS cnt FROM users;")
      user_count = cursor.fetchone()["cnt"]

      if user_count == 0:
        demo_pwd = generate_password_hash("1234")
        cursor.execute(
            """
                    INSERT INTO users (username, password_hash, nickname)
                    VALUES (%s, %s, %s), (%s, %s, %s)
                """,
            (
                "admin",
                demo_pwd,
                "관리자",
                "testuser",
                demo_pwd,
                "홍길동",
            ),
        )
        conn.commit()

        # 생성된 유저 ID 조회
        cursor.execute("SELECT id, username FROM users;")
        users = {u["username"]: u["id"] for u in cursor.fetchall()}
        admin_id = users.get("admin", 1)
        test_id = users.get("testuser", 2)

        # 샘플 게시글 15개 생성 (커서 페이징 및 필터/검색 테스트용)
        sample_posts = [
            (
                admin_id,
                "[공지] RESTful 게시판 시스템 오픈 안내",
                (
                    "Flask + MySQL + JWT + Tailwind CSS 기반의 RESTful 게시판이"
                    " 오픈되었습니다.\n커서 기반 페이징과 검색/필터 기능을"
                    " 제공합니다."
                ),
                "공지",
                120,
            ),
            (
                admin_id,
                "[공지] 커서 기반 페이징(Cursor-based Pagination) 가이드",
                (
                    "커서 기반 페이징은 OFFSET의 성능 한계를 극복하고 대용량"
                    " 데이터에서도 O(1) 수준의 빠른 조회를 지원합니다."
                ),
                "공지",
                85,
            ),
            (
                test_id,
                "Flask와 PyMySQL 연동 팁 공유",
                (
                    "DictCursor를 사용하면 딕셔너리 형태로 데이터를 편리하게"
                    " 조작할 수 있습니다."
                ),
                "팁",
                34,
            ),
            (
                test_id,
                "Tailwind CSS CDN으로 빠른 프로토타이핑하기",
                (
                    "Tailwind CSS는 유틸리티 우선 CSS 프레임워크로 별도 빌드 없이"
                    " CDN만으로도 강력합니다."
                ),
                "팁",
                42,
            ),
            (
                test_id,
                "JWT 토큰 기반 인증 흐름 질문입니다.",
                (
                    "클라이언트 로컬스토리지에 저장하고 Authorization 헤더에"
                    " Bearer 토큰으로 보내는 구조가 맞나요?"
                ),
                "질문",
                15,
            ),
            (
                admin_id,
                "JWT 인증 답변 드립니다.",
                (
                    "네, 맞습니다! Authorization: Bearer <token> 형식을"
                    " 표준으로 사용합니다."
                ),
                "정보",
                29,
            ),
            (
                test_id,
                "Docker Desktop에서 MySQL 컨테이너 관리하기",
                (
                    "포트 포워딩 3306:3306 설정을 해두면 로컬 호스트에서 바로"
                    " 접근 가능합니다."
                ),
                "정보",
                67,
            ),
            (
                test_id,
                "오늘 날씨가 정말 좋네요!",
                "다들 즐거운 코딩 하루 보내세요~ 화이팅입니다.",
                "자유",
                12,
            ),
            (
                admin_id,
                "게시판 검색 및 필터링 기능 테스트 글",
                (
                    "카테고리 필터와 제목/내용/작성자 검색이 정상적으로"
                    " 작동하는지 테스트합니다."
                ),
                "정보",
                54,
            ),
            (
                test_id,
                "파이썬 3.14 버전 써보신 분 계신가요?",
                (
                    "새로운 기능들이 많이 추가되었는데 성능 체감이"
                    " 어떠신가요?"
                ),
                "질문",
                23,
            ),
            (
                test_id,
                "RESTful API 엔드포인트 네이밍 규칙 정리",
                (
                    "GET /api/posts, POST /api/posts, PUT /api/posts/:id, DELETE"
                    " /api/posts/:id 표준 규칙 준수"
                ),
                "팁",
                78,
            ),
            (
                admin_id,
                "커서 페이징에서 다음 커서(next_cursor) 전달 방식",
                (
                    "응답 JSON에 next_cursor와 has_more 플래그를 포함하여"
                    " 클라이언트가 무한스크롤 또는 더보기를 구현합니다."
                ),
                "팁",
                91,
            ),
        ]

        cursor.executemany(
            """
                    INSERT INTO posts (user_id, title, content, category, views)
                    VALUES (%s, %s, %s, %s, %s)
                """,
            sample_posts,
        )
        conn.commit()

    conn.commit()
    print("[DB] Database & tables initialized successfully.")
  except Exception as e:
    conn.rollback()
    print(f"[DB Error] {e}")
    raise e
  finally:
    conn.close()
