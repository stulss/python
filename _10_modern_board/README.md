# 🛡️ SecBoard — 엔지니어링 커뮤니티 & 실시간 보안 관제 콘솔

> **Python 3.10+ / Flask 3.0 / Docker MySQL 8.0 / Flask-JWT-Extended / Tailwind CSS / Chart.js**  
> AI 특유의 인위적인 네온/가짜 테크 문구를 완전히 배제하고, **Linear / Datadog / GitHub 스타일의 모던 다크 엔지니어링 포털** 감성으로 정제된 고성능 풀스택 웹 애플리케이션입니다.

---

## 🌟 주요 핵심 기능

1. **RESTful Architecture & JWT 무상태 인증**
   - RFC 표준 상태 코드(200, 201, 400, 401, 403, 404, 500) 및 JSON 일관성 유지.
   - `Authorization: Bearer <JWT>` 헤더 기반의 보안 세션 및 3단계 RBAC (`user` / `gold` / `admin`).

2. **커서 기반 페이징 (Cursor-based Pagination)**
   - 대용량 데이터에서 성능이 저하되는 기존 `OFFSET` 방식 대신, B-Tree Primary Key 인덱스 조건을 직접 타는 `id < :cursor ORDER BY id DESC LIMIT :limit` 방식으로 **O(1) 수준의 초고속 페이징** 구현.
   - 응답 스키마: `{ items: [...], next_cursor: 8, has_more: true }`
   - 프론트엔드에서 끊김 없는 "다음 게시글 더보기" 연동.

3. **게시판 종합 CRUD & 인터랙션 & 등급별 열람 통제**
   - 글 작성, 상세 조회(조회수 증가), 글 수정/삭제(작성자 및 관리자 권한 검증).
   - **보안 관련 글 열람 통제**: `보안이슈` 카테고리 게시글은 **골드(Gold) 등급 이상(`gold`, `admin`)만 목록 노출 및 상세 조회/작성 가능** (일반회원 및 비로그인 접근 시 목록 자동 마스킹 및 403 차단).
   - 실시간 다중 조건 검색 (제목, 본문, 작성자, 태그).
   - 카테고리 필터링 (`공지사항`, `기술Q&A`, `보안이슈 (골드)`, `팁&노하우`, `자유게시판`).
   - 추천(좋아요) 카운팅 및 실시간 댓글 CRUD.

4. **보안 관제 센터 (Security Dashboard)**
   - 실시간 위협 수준 인디케이터 (`SECURE`, `ELEVATED`, `HIGH`, `CRITICAL`).
   - 최근 7일간의 보안 위협 발생 추이 멀티라인 차트 & 이벤트 유형 분포 도넛 차트 (Chart.js).
   - 실시간 보안 감사 로그(Audit Trail) 피드 & 심각도 필터.
   - **보안 이벤트 모의 테스트**: `SQL Injection`, `Brute-force`, `401 Unauthorized`, `XSS`, `권한 상승` 시도를 원클릭 발생시켜 SIEM 감지 테스트.

5. **관리자 대시보드 (Admin Console & RBAC)**
   - 사용자 역할 순환 변경 (`user` ➔ `gold` ➔ `admin`), 계정 상태 토글 (정상 ↔ 정지), 회원 영구 삭제.
   - 전역 게시글 강제 모니터링 및 즉각 삭제 조치.
   - 시스템 사용자 및 게시글 지표 실시간 표시.

6. **세련된 모던 다크 UI/UX (AI 느낌 완전 배제)**
   - 번쩍거리는 네온 광선과 어색한 가짜 지표 대신, 단정하고 신뢰감 있는 슬레이트 톤과 명확한 타이포그래피.
   - 가독성 높은 3열 반응형 게시글 카드, 본문 요약, 카테고리 뱃지 및 메트릭스.
   - 실제 활용 가능한 사이드바 (글쓰기, 보안 요약, 인기 해시태그 검색, 트래픽 추이 차트).

---

## 📂 프로젝트 구조

```text
_10_modern_board/
├── .env.example            # 환경변수 템플릿
├── .env                    # 실제 환경변수 (DB URL, JWT Secret 등)
├── requirements.txt        # 의존성 패키지 목록
├── config.py               # Flask 설정 클래스
├── extensions.py           # SQLAlchemy, JWTManager, CORS 인스턴스
├── models.py               # User, Post, Comment, SecurityLog DB 모델
├── app.py                  # Flask Application Factory 및 에러 핸들러
├── run.py                  # 서버 구동 엔트리포인트 (기본: http://127.0.0.1:5000)
├── init_db.py              # DB 생성 및 샘플 데이터(유저 5명, 글 12개, 댓글, 보안로그) 자동 주입
├── routes/
│   ├── __init__.py
│   ├── auth.py             # 회원가입, 로그인, JWT 발급
│   ├── posts.py            # 게시글 CRUD, 커서 페이징, 댓글, 좋아요
│   ├── admin.py            # 관리자 전용 통계, 유저 권한/상태 제어, 글 삭제
│   └── security.py         # 보안 통계, 로그 목록, 모의 위협 시뮬레이터
├── static/
│   ├── css/style.css       # 스크린샷 1:1 매칭 하이테크 스타일 & 폰트
│   └── js/
│       ├── app.js          # 전역 세션, JWT 인증, 모달, 시계 Ticker
│       ├── board.js        # 커서 페이징, 매트릭스 카드 렌더링, Load 차트
│       ├── security.js     # Chart.js 시각화, 실시간 로그, 위협 시뮬레이터
│       └── admin.js        # RBAC 유저 관리, 글 강제 삭제
└── templates/
    └── index.html          # 스크린샷 일치 단일 반응형 퓨처리즘 레이아웃
```

---

## ⚡ 빠른 시작 가이드 (명령어 복사 & 붙여넣기)

### 1단계: 프로젝트 폴더 이동
```powershell
cd C:\Users\user\Desktop\Aleph\python\_10_modern_board
```

### 2단계: 필수 패키지 설치
이미 가상환경에 설치되어 있으나, 신규 환경일 경우 아래 명령어를 실행합니다:
```powershell
pip install -r requirements.txt
```

### 3단계: Docker MySQL 컨테이너 확인
현재 Docker Desktop에서 실행 중인 MySQL 컨테이너(`flask_mysql`, 포트 3306)를 사용합니다.
```powershell
docker ps
```
> 만약 MySQL 접속 정보가 다를 경우 `.env` 파일의 `DATABASE_URL`을 수정하세요:  
> `DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/modern_board_db`

### 4단계: 데이터베이스 및 샘플 데이터 자동 초기화
```powershell
python init_db.py
```
*(성공 시: `[OK] MySQL Database 'modern_board_db' checked/created.` 와 함께 유저 5명, 게시글 12개, 댓글 5개, 보안 로그 6건이 자동 주입됩니다)*

### 5단계: 웹 서버 구동
```powershell
python run.py
```
브라우저에서 아래 주소로 접속합니다:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 기본 제공 테스트 계정 (3단계 권한 체계 & 1234 비밀번호)

| 계정명 | 비밀번호 | 닉네임 | 권한(Role) | 접근 가능 영역 | 설명 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **admin** | `1234` | 관리자 | **ADMIN (관리자)** | 게시판 + 보안 대시보드 + 관리자 콘솔 | 전체 시스템 관제, 회원 권한/상태 제어, 게시글 강제 삭제 |
| **golduser** | `1234` | 골드회원 | **GOLD (골드)** | 게시판 + 보안 대시보드 | **보안 관제 대시보드 열람 및 시뮬레이션 제어 권한 보유** |
| **testuser** | `1234` | 홍길동 | **USER (일반)** | 게시판 전용 | 일반 커뮤니티 활동 (글쓰기, 댓글, 추천). 보안/관리자 콘솔 차단 |
| **soarbot** | `1234` | 보안봇 | **ADMIN (봇)** | 시스템 내부 연동 | n8n SOAR 보안 자동화 및 차단 시 경보 공지 자동 등록 |

> 💡 상단 우측의 **[👑 관리자]**, **[⭐ 골드]**, **[👤 일반]** 원클릭 데모 버튼을 누르면 각각의 계정으로 1초 만에 즉시 전환 로그인하여 권한별 차등 UI를 테스트할 수 있습니다.

---

## 📡 RESTful API 엔드포인트 명세

### 1. 인증 API (`/api/auth`)
- `POST /api/auth/register` : 회원가입 (`{ username, nickname, password, email }`)
- `POST /api/auth/login` : 로그인 및 JWT Access Token 발급 (`{ username, password }`)
- `GET /api/auth/me` : 현재 로그인된 사용자 정보 조회 (`Authorization: Bearer <Token>`)

### 2. 게시판 API (`/api/posts`)
- `GET /api/posts` : 게시글 목록 조회
  - 파라미터: `cursor` (이전 페이지 마지막 id), `limit` (기본 6), `category`, `search`, `sort`
  - 반환: `{ items: [...], next_cursor: 8, has_more: true, total_count: 12 }`
- `POST /api/posts` : 게시글 작성 (JWT 필요)
- `GET /api/posts/<id>` : 게시글 상세 조회 및 조회수 증가
- `PUT /api/posts/<id>` : 게시글 수정 (작성자 또는 관리자)
- `DELETE /api/posts/<id>` : 게시글 삭제 (작성자 또는 관리자)
- `POST /api/posts/<id>/like` : 게시글 추천(좋아요) 증가
- `POST /api/posts/<id>/comments` : 댓글 작성
- `DELETE /api/posts/<id>/comments/<cid>` : 댓글 삭제

### 3. 보안 관제 & n8n SOAR 연동 API (`/api/security`)
- `POST /api/security/events` : **n8n SOAR 판정 이벤트 저장 (`X-API-Key` 헤더 인증, 거부 시 보안봇 자동 공지)**
- `GET /api/security/events` : 보안 이벤트 목록 조회 (`?student=&decision=&src_ip=`)
- `GET /api/security/stats` : **보안 통계 및 차트 데이터 (골드/관리자 전용, `@gold_required`)**
- `GET /api/security/logs` : **실시간 감사 로그 목록 (골드/관리자 전용, `@gold_required`)**
- `POST /api/security/simulate` : **모의 위협 시뮬레이션 발생 (골드/관리자 전용, `@gold_required`)**
- `POST /api/security/clear` : **보안 로그 초기화 (골드/관리자 전용, `@gold_required`)**

### 4. 공공데이터 Open API (`/api/openapi`)
- `GET /api/openapi/busan-themes` : **부산 테마여행정보 100선 및 공공데이터포털 실시간 연동** (`?gugun=&search=`)

### 5. 관리자 API (`/api/admin`)
- `GET /api/admin/stats` : 시스템 및 사용자 종합 지표 (관리자 전용, `@admin_required`)
- `GET /api/admin/users` : 전체 사용자 목록
- `PATCH /api/admin/users/<id>/role` : 권한 변경 (`user` ↔ `gold` ↔ `admin` 순환)
- `PATCH /api/admin/users/<id>/status` : 계정 상태 정지/활성화 토글
- `DELETE /api/admin/users/<id>` : 사용자 영구 삭제
- `GET /api/admin/posts` : 전체 게시글 목록
- `DELETE /api/admin/posts/<id>` : 관리자 강제 삭제

