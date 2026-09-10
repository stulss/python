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
    """데이터베이스, 테이블 자동 생성 및 초기 테스트 계정 주입"""
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
            # 1. DB 생성
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            cursor.execute(f"USE `{Config.DB_NAME}`;")

            # 2. 카페 유저 테이블 (role_level: 0=일반, 1=골드, 2=관리자)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cafe_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    nickname VARCHAR(50) NOT NULL,
                    role_level INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_role (role_level)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 3. 카페 게시글 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cafe_posts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    category VARCHAR(50) NOT NULL DEFAULT '이야기',
                    min_role INT NOT NULL DEFAULT 0,
                    views INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_posts_cafe_user FOREIGN KEY (user_id) REFERENCES cafe_users(id) ON DELETE CASCADE,
                    INDEX idx_id_desc (id DESC),
                    INDEX idx_category (category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 4. 초기 계정 존재 여부 확인
            cursor.execute("SELECT COUNT(*) AS cnt FROM cafe_users;")
            user_count = cursor.fetchone()["cnt"]

            if user_count == 0:
                print("[DB] 기본 계정 3종 생성 중 (관리자 Lv.2, 골드 Lv.1, 일반 Lv.0)...")
                pwd_hash = generate_password_hash("1234")

                users_data = [
                    ("admin", pwd_hash, "카페운영자", Config.ROLE_ADMIN),
                    ("golduser", pwd_hash, "골드바리스타", Config.ROLE_GOLD),
                    ("user1", pwd_hash, "새싹원두", Config.ROLE_USER),
                ]
                cursor.executemany("""
                    INSERT INTO cafe_users (username, password_hash, nickname, role_level)
                    VALUES (%s, %s, %s, %s);
                """, users_data)
                conn.commit()

                # 유저 ID 매핑
                cursor.execute("SELECT id, username FROM cafe_users;")
                user_map = {u["username"]: u["id"] for u in cursor.fetchall()}

                # 샘플 게시글 주입
                sample_posts = [
                    (
                        user_map["admin"],
                        "[공지] ☕ 카페이야기 커뮤니티 오픈 & 권한 시스템 안내",
                        "카페이야기에 오신 것을 환영합니다!\n본 시스템은 일반회원(Lv.0), 골드회원(Lv.1, 중간관리자), 관리자(Lv.2) 3단계의 접근 제어가 적용되어 있습니다.\n골드 라운지와 관리자 페이지를 직접 체험해보세요.",
                        "공지",
                        0,
                        189
                    ),
                    (
                        user_map["golduser"],
                        "[VIP 레시피] 골드회원 전용 에티오피아 핸드드립 가이드",
                        "골드 등급 회원님들을 위한 스페셜 핸드드립 가이드입니다.\n물 온도 91도, 뜸 들이기 40초를 통해 화사한 자스민 향과 블루베리 산미를 극대화할 수 있습니다.",
                        "추천메뉴",
                        1,
                        105
                    ),
                    (
                        user_map["user1"],
                        "오늘 아침에 마신 따뜻한 아메리카노 한 잔",
                        "날씨가 쌀쌀할 때는 따뜻한 아메리카노가 최고네요! 다들 오늘 하루도 힘내세요~",
                        "이야기",
                        0,
                        42
                    ),
                    (
                        user_map["admin"],
                        "[안내] 골드 등급(중간 관리자) 승급 기준 안내",
                        "카페 게시글 5개 이상 작성 및 활동 우수 회원에게 골드 등급(Lv.1)이 부여됩니다.\n골드 등급은 골드 라운지 출입 및 메뉴 추천 권한을 갖습니다.",
                        "공지",
                        0,
                        97
                    ),
                    (
                        user_map["golduser"],
                        "[골드라운지] 9월 카페 원두 공동구매 의견 수렴",
                        "중간관리자 라운지에서 진행하는 9월 스페셜티 원두 공동구매 후보 목록입니다. 의견 남겨주세요!",
                        "이야기",
                        1,
                        76
                    ),
                ]
                cursor.executemany("""
                    INSERT INTO cafe_posts (user_id, title, content, category, min_role, views)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, sample_posts)
                conn.commit()

        conn.commit()
        print("[DB] 카페이야기 데이터베이스 및 테이블 초기화 완료!")
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] {e}")
        raise e
    finally:
        conn.close()
