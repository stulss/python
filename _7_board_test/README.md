# 🚀 Flask RESTful 커서 페이징 게시판 (REST Board)

Windows 11, Docker MySQL, Flask, PyJWT, Tailwind CSS 기반의 RESTful 게시판 시스템입니다.

---

## 📌 주요 특징 및 기능

1. **RESTful API 아키텍처**
   - 표준 HTTP 메서드(`GET`, `POST`, `PUT`, `DELETE`) 및 상태 코드 준수
   - JSON 기반 요청 및 응답 포맷
2. **JWT (JSON Web Token) 인증**
   - 비밀번호 암호화 저장 (`generate_password_hash` / `check_password_hash`)
   - `Authorization: Bearer <JWT_TOKEN>` 헤더 기반 인증 데코레이터 (`@jwt_required`)
   - 본인이 작성한 게시글만 수정/삭제 가능한 권한 검증
3. **커서 기반 페이징 (Cursor-based Pagination)**
   - `OFFSET` 대신 `id < :cursor` 인덱스 기반 빠른 조회 (대용량 데이터 최적화)
   - `has_more` 및 `next_cursor` 응답 지원
   - "더 불러오기 (Load More)" 무한 누적 및 다음 커서 이동 기능
4. **검색 및 카테고리 필터링**
   - 카테고리별 실시간 필터 (`공지`, `자유`, `질문`, `팁`, `정보`)
   - 검색 조건 선택 (전체, 제목, 내용, 작성자)
5. **Tailwind CSS 반응형 UI**
   - 모바일, 태블릿, 데스크톱 완벽 대응
   - 모달 기반 로그인/회원가입/글작성/상세보기
   - 플로팅 토스트 알림 메시지

---

## 📂 프로젝트 구조

```
_7_board_test/
├── .env                  # 환경 변수 (DB 및 JWT 설정)
├── requirements.txt      # 파이썬 의존성 패키지 목록
├── docker-compose.yml    # Docker MySQL 설정
├── config.py             # 설정 로더
├── db.py                 # MySQL 연결 및 자동 테이블/샘플데이터 초기화
├── auth.py               # JWT 생성, 검증 및 @jwt_required 데코레이터
├── app.py                # Flask 메인 애플리케이션 진입점
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py    # 회원가입, 로그인, 내 정보 REST API
│   └── post_routes.py    # 게시글 CRUD, 검색, 필터, 커서 페이징 API
├── templates/
│   └── index.html        # Tailwind CSS 반응형 UI 템플릿
└── static/
    └── js/
        └── app.js        # 클라이언트 비동기 통신 & UI 상태 관리
```

---

## ⚡ 빠른 실행 가이드 (Quick Start)

### 1. MySQL 컨테이너 확인 및 실행
Docker Desktop이 실행된 상태에서 아래 명령어 중 하나로 MySQL을 실행합니다.

```powershell
# 기존 생성된 컨테이너 시작 시:
docker start mysql-server

# 또는 docker-compose로 실행 시:
docker compose up -d
```

### 2. 패키지 설치
```powershell
pip install -r requirements.txt
```

### 3. Flask 서버 실행
```powershell
python app.py
```
> 서버가 실행되면 브라우저에서 `http://127.0.0.1:5000` 으로 접속하세요!
> 실행 시 자동으로 `board_db` 데이터베이스 및 테이블이 생성되고 테스트용 샘플 데이터가 주입됩니다.

---

## 🔑 기본 제공 테스트 계정

| 아이디 | 비밀번호 | 닉네임 | 권한 |
| :--- | :--- | :--- | :--- |
| `admin` | `1234` | 관리자 | 관리자 샘플 계정 |
| `testuser` | `1234` | 홍길동 | 일반 회원 샘플 계정 |

*(회원가입 모달에서 언제든 새로운 계정을 직접 생성할 수도 있습니다.)*

---

## 📡 RESTful API 엔드포인트 명세

### 1. 인증 (Auth) API

| Method | Endpoint | Description | Auth 필요 |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/auth/register` | 회원가입 | ❌ |
| `POST` | `/api/auth/login` | 로그인 (JWT 발급) | ❌ |
| `GET` | `/api/auth/me` | 현재 사용자 정보 조회 | ⭕ |

### 2. 게시글 (Posts) API

| Method | Endpoint | Description | Auth 필요 |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/categories` | 카테고리 목록 및 개수 조회 | ❌ |
| `GET` | `/api/posts` | 게시글 목록 조회 (커서 페이징, 필터, 검색) | ❌ |
| `GET` | `/api/posts/<id>` | 게시글 상세 조회 (조회수 +1) | ❌ (선택) |
| `POST` | `/api/posts` | 새 게시글 작성 | ⭕ |
| `PUT` | `/api/posts/<id>` | 게시글 수정 (작성자 전용) | ⭕ |
| `DELETE` | `/api/posts/<id>` | 게시글 삭제 (작성자 전용) | ⭕ |

---

## 🧪 cURL 테스트 명령어 예시

### 1. 로그인하여 JWT 토큰 얻기
```powershell
curl -X POST http://127.0.0.1:5000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"admin\",\"password\":\"1234\"}'
```

### 2. 커서 기반 페이징으로 게시글 목록 조회 (1페이지 4개)
```powershell
curl -X GET "http://127.0.0.1:5000/api/posts?limit=4"
```

### 3. 다음 커서로 2페이지 조회 (예: cursor=9)
```powershell
curl -X GET "http://127.0.0.1:5000/api/posts?limit=4&cursor=9"
```

### 4. 카테고리 필터 및 검색 조회
```powershell
curl -X GET "http://127.0.0.1:5000/api/posts?category=팁&search=Flask&search_type=all"
```

### 5. 새 글 작성 (JWT Bearer 토큰 필요)
```powershell
curl -X POST http://127.0.0.1:5000/api/posts `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer <여기에_토큰_입력>" `
  -d '{\"title\":\"RESTful API 테스트\",\"content\":\"내용입니다.\",\"category\":\"자유\"}'
```
