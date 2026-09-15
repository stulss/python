"""[주석·설명용 사본] controllers/post_controller.py — 게시글 CRUD (RESTful). 쓰기/수정/삭제는 JWT 로그인 필요

이 파일은 원본 controllers/post_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 import 한다(controllers/__init__.py 의 from .post_controller import post_bp).
    이 사본은 블루프린트로 등록되지 않는다. 파일 이름에 공백이 있어 import 문으로 부를 수도 없다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "게시글을 목록 조회(누구나)·작성·수정·삭제(로그인 필요, 수정·삭제는 작성자 본인만)하는
   REST API. 목록은 '더보기' 버튼용 커서 방식으로 5개씩 끊어 준다."

==============================================================================
1. 쉬운 비유 — 아파트 1층 코르크 게시판
==============================================================================
  posts 테이블              = 게시판에 꽂힌 쪽지들
  GET    /api/posts         = 게시판 구경 (아무나)
  POST   /api/posts         = 쪽지 붙이기 (주민증 필요)
  PUT    /api/posts/<id>    = 쪽지 고쳐 쓰기 (붙인 사람만)
  DELETE /api/posts/<id>    = 쪽지 떼기 (붙인 사람만)
  JWT 토큰                  = 관리사무소가 발급한 주민증(위조 방지 도장, 2시간 유효)
  @jwt_required()           = 게시판 앞 경비원 — 주민증부터 확인
  author_id 비교             = "이 쪽지, 선생님이 붙인 거 맞으세요?" 확인
  cursor(커서)               = 책갈피 — "마지막으로 본 쪽지 번호보다 오래된 것부터 보여 주세요"

  구경은 누구나 한다. 쪽지를 붙이려면 경비원에게 주민증을 보여야 하고(인증),
  남이 붙인 쪽지는 주민증이 있어도 고치거나 뗄 수 없다(인가).
  쪽지가 많으면 한 번에 5장만 보여 주고 "더보기"를 누르면 책갈피 다음부터 5장을 더 보여 준다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ REST 와 CRUD
      주소(자원)는 하나로 두고, 무엇을 할지는 HTTP 메서드로 구분한다.
        Create → POST   /api/posts          Read   → GET    /api/posts
        Update → PUT    /api/posts/<id>     Delete → DELETE /api/posts/<id>
      이 파일에는 '글 1건 조회(GET /api/posts/<id>)' 는 없다. 목록 응답에 본문까지 들어 있다.

  ■ HTTP 상태코드 (이 파일에서 나오는 것)
      200 OK / 201 Created(새로 만듦) / 400 Bad Request(필수값 누락)
      401 Unauthorized(로그인 안 함·토큰 만료) / 403 Forbidden(남의 글)
      404 Not Found(없는 글) / 422 Unprocessable Entity(토큰 형식·서명 오류, flask_jwt_extended 기본)

  ■ Blueprint
      관련 라우트를 묶은 '부서'. url_prefix='/api/posts' 에 라우트 '' 또는 '/<int:id>' 가 붙는다.
      app.py 가 controllers/__init__.py 의 all_blueprints 를 돌며 등록한다.

  ■ 인증(Authentication) vs 인가(Authorization)
      인증 = "너 누구야?"         → @jwt_required() 가 토큰을 검사. 실패하면 401/422
      인가 = "너 이거 해도 돼?"   → post.author_id != user_id 비교. 실패하면 403
      주의: 여기서의 인가는 '작성자 본인인가'만 본다. role(user/gold/admin)은 보지 않는다.

  ■ JWT 와 @jwt_required()
      로그인(POST /api/auth/login, auth_controller.py)이 create_access_token(identity=str(user.id))
      로 토큰을 만들어 준다. 화면(index.html)은 토큰을 localStorage 에 두었다가
      요청 헤더  Authorization: Bearer <토큰>  으로 보낸다(flask_jwt_extended 기본 헤더 규칙).
      get_jwt_identity() 는 토큰 속 identity, 즉 문자열 "3" 같은 사용자 id 를 돌려준다
      → DB 의 정수 author_id 와 비교하려고 int() 로 바꾼다.
      유효시간은 config.py 의 JWT_ACCESS_TOKEN_EXPIRES = 2시간.

  ■ ORM (Flask-SQLAlchemy)
      SQL 을 직접 쓰지 않고 파이썬 객체로 DB 를 다룬다.
        Post.query                 → SELECT ... FROM posts 준비
        .filter(조건) / .like()     → WHERE ... / LIKE '%...%'
        .order_by(Post.id.desc())  → ORDER BY id DESC
        .limit(n).all()            → LIMIT n 으로 실행해 리스트로 받기
        Post.query.get_or_404(id)  → 기본키로 1건. 없으면 곧바로 404 로 중단
        db.session.add / delete    → 변경 예약(아직 DB 에 확정 안 됨)
        db.session.commit()        → 예약한 변경을 DB 에 확정
      참고: get_or_404 안에서 쓰는 Query.get 은 SQLAlchemy 2.0 에서 '레거시(legacy)' 표시가 붙은 API 다.
            대안은 db.session.get(Post, id) — app.py·rbac.py 는 이미 이 방식을 쓴다.

  ■ 커서(cursor) 기반 페이지 vs 오프셋(offset) 페이지
      오프셋: "앞에서 10개 건너뛰고 5개" — 그 사이 새 글이 생기면 목록이 밀려 중복·누락이 생긴다.
      커서  : "id 가 8 보다 작은 것 중 5개" — 기준이 '마지막으로 본 글 번호'라 밀리지 않는다.
      다음 페이지 유무는 limit+1 개를 가져와 판단한다(1개가 더 오면 뒤에 더 있다는 뜻).

  ■ request.args.get(이름, default=, type=)
      쿼리스트링 값을 꺼낸다. type=int 변환에 실패하면(예: limit=abc) 에러 대신 default 를 돌려준다
      (설치된 Werkzeug 3.0.1 동작). default 가 없으면 None.

  ■ request.get_json(silent=True) or {}
      JSON 본문을 dict 로. 본문이 없거나 JSON 이 아니면 silent=True 라 예외 대신 None → or {} 로 빈 dict.

==============================================================================
3. 동작 원리
==============================================================================
  ■ 목록 (GET /api/posts)
     요청 → cursor·limit·search·category 읽기
          → category 필터(''·'전체' 는 건너뜀) → search 필터(제목 OR 내용) → cursor 필터(id < cursor)
          → id 내림차순으로 limit+1 개 조회
          → limit 보다 많이 왔으면 has_more=True, 마지막 1개 버리고 next_cursor = 남은 마지막 글 id
          → {"posts": [...], "next_cursor": ..., "has_more": ...} (200)

     예) 글 id 가 1~12, limit=5
       1회차 cursor 없음  → LIMIT 6 → [12,11,10,9,8,7] → 5개만 [12..8], next_cursor=8,  has_more=true
       2회차 cursor=8     → id<8   → [7,6,5,4,3,2]    → 5개만 [7..3],  next_cursor=3,  has_more=true
       3회차 cursor=3     → id<3   → [2,1]            → 그대로,        next_cursor=null, has_more=false

  ■ 작성 (POST /api/posts)
     요청 → @jwt_required() 토큰 검사(실패 401/422) → user_id = 토큰 속 id
          → title·content 비었으면 400 → Post 생성(category 기본 '일반', author_id=user_id)
          → add → commit(이때 id 가 정해진다) → {"msg", "id"} (201)

  ■ 수정·삭제 (PUT·DELETE /api/posts/<id>)
     요청 → @jwt_required() → user_id
          → get_or_404(id) (없으면 404)
          → post.author_id != user_id 면 403
          → 수정: 보낸 필드만 덮어쓰기 / 삭제: session.delete
          → commit → {"msg"} (200)

  ■ 누가 부르나 — templates/index.html 의 JS
       loadPosts()   : GET /api/posts?limit=5&search=..&category=..&cursor=..  (검색·필터·더보기)
       submitPost()  : 새 글이면 POST /api/posts, 수정이면 PUT /api/posts/<id>  (Bearer 토큰 첨부)
       deletePost()  : DELETE /api/posts/<id>                                    (Bearer 토큰 첨부)
       '수정·삭제' 버튼은 post.author 가 내 username 과 같을 때만 그린다(화면 편의일 뿐, 실제 검사는 서버).

==============================================================================
4. 옵션 설명
==============================================================================
  ■ 엔드포인트
    | 메서드 | URL              | 인증/인가          | 쿼리 파라미터                         | body                          | 응답 코드            |
    |--------|------------------|--------------------|---------------------------------------|-------------------------------|----------------------|
    | GET    | /api/posts       | 없음(누구나)        | cursor, limit, search, category        | 없음                          | 200                  |
    | POST   | /api/posts       | JWT 필수           | 없음                                  | title*, content*, category    | 201/400/401/422      |
    | PUT    | /api/posts/<id>  | JWT + 작성자 본인   | 없음                                  | title, content, category(선택) | 200/401/403/404/422  |
    | DELETE | /api/posts/<id>  | JWT + 작성자 본인   | 없음                                  | 없음                          | 200/401/403/404/422  |
      * = 필수.  <id> 는 <int:id> 라 숫자가 아니면 주소가 맞지 않아 404.
      끝에 / 를 붙인 /api/posts/ 는 다른 주소로 취급되어 404.
      GET /api/posts/<id> 는 주소는 맞지만 GET 이 허용되지 않아 405.

  ■ GET 쿼리 파라미터
    | 이름      | 타입 | 기본값 | 뜻                                        | 이상한 값을 주면                 |
    |-----------|------|--------|-------------------------------------------|----------------------------------|
    | cursor    | int  | 없음   | 이 id 보다 작은(오래된) 글만               | 숫자 아님·0 → 처음부터            |
    | limit     | int  | 5      | 한 번에 받을 개수                          | 숫자 아님 → 5 / 상한 없음 / 0 이하 → 함정 ② |
    | search    | str  | ''     | 제목 또는 내용에 포함(LIKE '%검색어%')      | % 와 _ 는 와일드카드로 동작       |
    | category  | str  | ''     | 카테고리 정확히 일치                       | '' 또는 '전체' → 필터 안 함        |
      화면의 카테고리 선택지: 전체 / 일반 / 공지 / 질문 / 골드 (서버는 값 목록을 검사하지 않는다)

  ■ body 필드 (JSON, Content-Type: application/json)
    | 필드      | POST 작성                        | PUT 수정                          |
    |-----------|----------------------------------|-----------------------------------|
    | title     | 필수(없거나 '' 이면 400)          | 선택 — 보내면 그 값으로, 안 보내면 그대로 |
    | content   | 필수(없거나 '' 이면 400)          | 선택 — 위와 같음                   |
    | category  | 선택, 기본 '일반'                 | 선택 — 위와 같음                   |

  ■ 응답 모양
    목록 : {"posts": [Post.to_dict(), ...], "next_cursor": 정수 또는 null, "has_more": true/false}
           Post.to_dict() = {"id", "title", "content", "category", "author"(작성자 username), "author_id"}
    작성 : {"msg": "게시글이 등록되었습니다.", "id": 새 글 번호}          201
    수정 : {"msg": "수정되었습니다."}                                     200
    삭제 : {"msg": "삭제되었습니다."}                                     200
    400  : {"msg": "title, content 는 필수입니다."}
    403  : {"msg": "권한이 없습니다."}
    404  : get_or_404 가 멈춘 것 — JSON 이 아니라 HTML 오류 페이지(함정 ③)

  ■ JWT 가 실패했을 때 (flask_jwt_extended 4.6.0 기본 응답 — 이 앱은 바꾸지 않았다)
    | 상황                                    | 코드 | 응답                                             |
    |-----------------------------------------|------|--------------------------------------------------|
    | Authorization 헤더가 없음                | 401  | {"msg": "Missing Authorization Header"}          |
    | 헤더에 Bearer 없이 토큰만                 | 401  | {"msg": "Missing 'Bearer' type in 'Authorization' header. ..."} |
    | 토큰이 망가짐·서명 불일치(다른 비밀키)     | 422  | {"msg": "<오류 이유>"}                            |
    | 토큰 유효시간(2시간) 지남                 | 401  | {"msg": "Token has expired"}                     |

  ■ 데코레이터·함수 인자
    | 코드                                      | 설명                                                         |
    |-------------------------------------------|--------------------------------------------------------------|
    | Blueprint('post', __name__, url_prefix=)   | 이름 'post' → 엔드포인트 이름 post.get_posts 등               |
    | @post_bp.route('', methods=['GET'])        | 규칙 '' = url_prefix 그대로(/api/posts). methods 로 허용 메서드 |
    | @post_bp.route('/<int:id>', ...)           | 주소 속 숫자를 int 로 바꿔 함수 인자 id 로 넘긴다              |
    | @jwt_required()                            | 괄호 필수(인자를 받아 데코레이터를 만들어 주는 함수).           |
    |                                            | 인자: optional=False, fresh=False, refresh=False, locations=None, |
    |                                            |       verify_type=True, skip_revocation_check=False — 전부 기본값 사용 |
    | get_jwt_identity()                         | 검사를 통과한 토큰의 identity(여기선 "사용자 id" 문자열)       |
    | request.args.get(key, default=, type=)     | 쿼리 값 꺼내기(변환 실패 시 default)                           |
    | request.get_json(silent=True)              | JSON 본문 → dict. 실패하면 None                               |

  ■ 관련 설정값 (config.py → flask_jwt_extended 가 사용)
    | 설정                        | 값                          | 비고                               |
    |-----------------------------|-----------------------------|------------------------------------|
    | JWT_SECRET_KEY              | .env (없으면 'dev-only-change-me') | 토큰 서명 키. 바뀌면 기존 토큰 전부 422 |
    | JWT_ACCESS_TOKEN_EXPIRES    | 2시간                        | 지나면 401 Token has expired        |
    | JWT_HEADER_NAME / TYPE      | Authorization / Bearer      | 라이브러리 기본값(config.py 에 없음)  |

==============================================================================
5. 요청·응답 예시   (토큰은 자리표시자. Windows PowerShell 은 curl 대신 curl.exe, 따옴표 규칙이 다르다)
==============================================================================
  ① 로그인해서 토큰 받기 (auth_controller.py)
    curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"username": "kim", "password": "<비밀번호>"}'
    → {"access_token": "<JWT>", "username": "kim", "role": "user", "role_label": "일반"}

  ② 목록 — 2개씩, 제목·내용에 flask 가 들어간 글
    curl "http://localhost:5000/api/posts?limit=2&search=flask"
    → {"posts": [{"id": 12, "title": "flask 질문", "content": "...", "category": "질문", "author": "kim", "author_id": 3},
                 {"id": 9,  "title": "...",        "content": "flask ...", "category": "일반", "author": "lee", "author_id": 4}],
       "next_cursor": 9, "has_more": true}
    다음 페이지: curl "http://localhost:5000/api/posts?limit=2&search=flask&cursor=9"

  ③ 작성
    curl -X POST http://localhost:5000/api/posts -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" -d '{"title": "첫 글", "content": "안녕하세요", "category": "질문"}'
    → 201 {"msg": "게시글이 등록되었습니다.", "id": 13}

  ④ 수정 — 제목만 바꾸기(나머지는 그대로 유지)
    curl -X PUT http://localhost:5000/api/posts/13 -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" -d '{"title": "제목만 수정"}'
    → 200 {"msg": "수정되었습니다."}
    남의 글이면 → 403 {"msg": "권한이 없습니다."}

  ⑤ 삭제
    curl -X DELETE http://localhost:5000/api/posts/13 -H "Authorization: Bearer <JWT>"
    → 200 {"msg": "삭제되었습니다."}      없는 번호면 → 404 (HTML)

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① '골드' 글이 일반 목록으로 샌다.
     GET /api/posts?category=골드 는 로그인·등급 검사 없이 골드 카테고리 글을 돌려준다.
     골드 전용 API(gold_controller.py 의 GET /api/gold/posts)는 등급이 없으면 403 으로 막지만
     이 파일의 목록에는 그런 검사가 없다. 작성 때도 category 를 검사하지 않아
     user 등급도 '골드' 글을 쓸 수 있다(index.html 의 글쓰기 선택지에 '골드'가 있다).
  ② limit 이 0 이하이면 500 이 난다.
     limit=0  : 조건에 맞는 글이 1개라도 있으면 has_more=True → posts[:0] 로 빈 리스트 → posts[-1] 에서 IndexError.
     limit=-1 : LIMIT 0 으로 빈 리스트인데 0 > -1 이라 has_more=True → 같은 IndexError.
     반대로 상한도 없어서 limit=100000 이면 글을 한 번에 전부 가져온다.
  ③ 404 응답은 JSON 이 아니다. get_or_404 는 abort(404) 로 멈추고, app.py 에 JSON 404 처리기가 없어서
     Werkzeug 의 HTML 오류 페이지가 간다. 화면 JS 가 res.json() 을 부르면 해석 오류가 난다
     (index.html 은 res.ok 만 보고 알림을 띄우므로 괜찮다).
  ④ PUT 은 '보낸 필드만' 바꾼다(엄밀한 REST 의 PUT 보다 PATCH 에 가깝다).
     그리고 POST 와 달리 빈 값 검사가 없다: {"title": ""} 로 제목을 빈 문자열로 만들 수 있다.
     {"title": null} 이면 None 이 들어가 NOT NULL 컬럼과 부딪혀 commit 에서 DB 오류(500)가 날 수 있다.
  ⑤ category 는 아무 문자열이나 저장된다. index.html 은 title·content 는 escapeHtml 로 감싸지만
     category 와 author 는 감싸지 않고 innerHTML 에 넣는다 → 스크립트가 든 category 를 저장하면
     목록을 여는 사람의 브라우저에서 실행될 수 있다(저장형 XSS).
  ⑥ 데코레이터 순서가 중요하다. @post_bp.route 가 맨 위, @jwt_required() 가 그 아래여야 한다.
     순서를 바꾸면 검사 없는 원래 함수가 라우트에 등록되어 로그인 없이 호출된다.
     @jwt_required 처럼 괄호를 빼도 제대로 동작하지 않는다.
  ⑦ search 의 % 와 _ 는 LIKE 와일드카드다(search=% → 모든 글). f-string 으로 만들었지만 값은
     SQLAlchemy 가 바인딩 파라미터로 보내므로 SQL 인젝션은 아니다. 앞에 % 가 붙은 LIKE 는
     인덱스를 쓰지 못해 글이 많아지면 느려진다.
  ⑧ admin 이라도 남의 글은 403 이다. 인가 기준이 role 이 아니라 author_id 뿐이기 때문이다.
     (그래서 security_controller 가 soarbot 계정 이름으로 올린 '보안' 공지글은 API 로 지울 사람이 없다)
  ⑨ 토큰은 2시간 뒤 만료(401 Token has expired). 그런데 index.html 은 localStorage 에 토큰이 남아 있으면
     계속 로그인 상태로 보여 주고, 실패 시 '처리에 실패했습니다.' / '삭제 권한이 없습니다.' 알림만 띄운다.
     이럴 땐 로그아웃 후 다시 로그인한다.
  ⑩ 서버는 길이를 검사하지 않는다. title 은 String(200) 컬럼이라 200자를 넘기면
     DB 설정에 따라 오류(500)가 나거나 잘린다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
#   Blueprint        : 라우트 묶음(부서) 만들기
#   jsonify          : dict → JSON 응답
#   request          : 지금 들어온 요청(쿼리스트링·본문·헤더)
#   get_jwt_identity : 검사를 통과한 토큰에서 identity(사용자 id 문자열) 꺼내기
#   jwt_required     : "유효한 토큰이 있어야 통과" 데코레이터
#   db               : extensions.py 의 SQLAlchemy 객체(세션 add/delete/commit 에 사용)
#   Post             : models/post.py 의 게시글 모델(posts 테이블)
# ─────────────────────────────────────────────────────────────────────────────
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models import Post

# 블루프린트 생성: 이름 'post', 이 파일의 모든 주소 앞에 /api/posts 가 붙는다.
post_bp = Blueprint('post', __name__, url_prefix='/api/posts')


# ═════════════════════════════════════════════════════════════════════════════
# get_posts() — 게시글 목록 (Read) · 커서 기반 '더보기'
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 게시판 구경. 최신 쪽지부터 5장 보여 주고, 책갈피(next_cursor)를 끼워 둔다.
#
# 입력: 쿼리스트링 ?cursor=&limit=&search=&category=   (전부 선택)
# 출력: 200 {"posts": [...], "next_cursor": id 또는 null, "has_more": bool}
# 인증: 없음 — 로그인하지 않아도 볼 수 있다
# 누가 호출하나: templates/index.html 의 loadPosts() (첫 화면, 검색, 카테고리 변경, 더보기)
# 주소: GET /api/posts   (규칙 '' 이라 url_prefix 그대로)
# ═════════════════════════════════════════════════════════════════════════════
@post_bp.route('', methods=['GET'])
def get_posts():
  """커서 기반 목록. ?cursor=&limit=&search=&category="""
  # ── ① 쿼리 파라미터 읽기 ──
  # cursor : 이 번호보다 작은(오래된) 글부터. 없거나 숫자가 아니면 None → 처음부터
  cursor = request.args.get('cursor', type=int)
  # limit : 한 번에 몇 개. 없거나 숫자가 아니면 5. (0 이하·상한 검사는 없다 — 함정 ②)
  limit = request.args.get('limit', default=5, type=int)
  # search : 제목/내용 검색어. 없으면 '' (빈 문자열은 거짓 → 아래에서 필터 안 함)
  search = request.args.get('search', default='', type=str)
  # category : 카테고리. index.html 은 기본으로 '전체' 를 보낸다
  category = request.args.get('category', default='', type=str)

  # ── ② 조회 조건 조립 ── 아직 DB 에 가지 않는다. 조건만 차곡차곡 붙인다.
  query = Post.query
  # '' 이나 '전체' 가 아니면 그 카테고리만 (정확히 일치)
  #   주의: 여기엔 등급 검사가 없어 '골드' 도 누구나 조회된다(함정 ①)
  if category and category != '전체':
    query = query.filter(Post.category == category)
  # 검색어가 있으면 "제목에 포함 OR 내용에 포함"
  if search:
    query = query.filter(
        # like('%검색어%') : 앞뒤 아무 글자나 와도 되는 부분 일치.  | 는 SQL 의 OR
        # f-string 이지만 SQLAlchemy 가 값을 바인딩 파라미터로 보내므로 SQL 인젝션은 아니다
        (Post.title.like(f'%{search}%')) | (Post.content.like(f'%{search}%'))
    )
  # 책갈피가 있으면 그보다 작은 id 만 → '이미 본 글 다음'부터
  if cursor:
    query = query.filter(Post.id < cursor)

  # ── ③ 실행 ── 최신(id 큰 것)부터, limit 보다 1개 더 가져온다.
  #   1개가 더 오면 "뒤에 글이 더 있다"는 증거 → 별도의 COUNT 쿼리가 필요 없다.
  posts = query.order_by(Post.id.desc()).limit(limit + 1).all()
  # 요청한 개수보다 많이 왔나?
  has_more = len(posts) > limit
  if has_more:
    # 확인용으로 더 가져온 마지막 1개는 버린다
    posts = posts[:limit]
    # 이번 페이지 마지막 글의 id = 다음 요청의 cursor
    #   (limit 이 0 이하이면 posts 가 비어 있어 여기서 IndexError → 500, 함정 ②)
    next_cursor = posts[-1].id
  else:
    # 더 없으면 책갈피도 없다 → JSON 에서 null
    next_cursor = None

  # ── ④ 응답 ── 모델 객체는 바로 JSON 이 안 되므로 to_dict() 로 dict 로 바꾼다
  #   to_dict() 는 author(작성자 username)도 넣는다 → 글마다 users 테이블 조회가 따라올 수 있다
  return jsonify({
      'posts': [p.to_dict() for p in posts],
      'next_cursor': next_cursor,
      'has_more': has_more,
  })


# ═════════════════════════════════════════════════════════════════════════════
# create_post() — 새 글 작성 (Create)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 주민증(토큰)을 보여 주고 쪽지를 붙인다. 쪽지에는 붙인 사람 번호(author_id)가 자동으로 적힌다.
#
# 입력: 헤더 Authorization: Bearer <토큰>
#       body {"title": 필수, "content": 필수, "category": 선택(기본 '일반')}
# 출력: 201 {"msg": "게시글이 등록되었습니다.", "id": 새 번호}
#       400 필수값 누락 / 401·422 토큰 문제
# 누가 호출하나: templates/index.html 의 submitPost() (edit-post-id 가 비어 있을 때)
# 주소: POST /api/posts
# ═════════════════════════════════════════════════════════════════════════════
@post_bp.route('', methods=['POST'])
# 토큰 검사 — 통과해야만 아래 함수 본문이 실행된다. 순서: route 위, jwt_required 아래(함정 ⑥)
@jwt_required()
def create_post():
  # 토큰 속 identity 는 로그인 때 넣은 str(user.id) → 정수로 바꿔 author_id 에 쓴다.
  # 작성자를 body 에서 받지 않고 토큰에서 꺼내므로 남의 이름으로 글을 쓸 수 없다.
  user_id = int(get_jwt_identity())
  # JSON 본문 → dict. 본문이 없거나 JSON 이 아니면 {} (→ 아래에서 400)
  data = request.get_json(silent=True) or {}
  # 제목·내용이 없거나 빈 문자열이면 거절
  if not data.get('title') or not data.get('content'):
    return jsonify({'msg': 'title, content 는 필수입니다.'}), 400

  # 새 글 객체. category 는 안 보내면 '일반'. (값 목록 검사는 없다 — 함정 ①⑤)
  post = Post(title=data['title'], content=data['content'],
              category=data.get('category', '일반'), author_id=user_id)
  # 세션에 추가(INSERT 예약)
  db.session.add(post)
  # DB 에 확정. 이 순간 AUTO_INCREMENT 로 post.id 가 채워진다
  db.session.commit()
  # 201 Created + 새 글 번호
  return jsonify({'msg': '게시글이 등록되었습니다.', 'id': post.id}), 201


# ═════════════════════════════════════════════════════════════════════════════
# update_post(id) — 글 수정 (Update) · 작성자 본인만
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 쪽지를 고쳐 쓰려면 주민증 확인(인증) + "당신이 붙인 쪽지인가" 확인(인가)을 둘 다 통과해야 한다.
#
# 입력: 주소의 id(정수), 헤더 Authorization: Bearer <토큰>
#       body {"title", "content", "category"} — 보낸 것만 바뀌고 나머지는 그대로
# 출력: 200 {"msg": "수정되었습니다."}
#       401·422 토큰 문제 / 404 없는 글(HTML) / 403 남의 글
# 누가 호출하나: templates/index.html 의 submitPost() (수정 모달에서 저장)
# 주소: PUT /api/posts/<id>
# ═════════════════════════════════════════════════════════════════════════════
@post_bp.route('/<int:id>', methods=['PUT'])
@jwt_required()
def update_post(id):
  # 요청한 사람의 사용자 번호
  user_id = int(get_jwt_identity())
  # 기본키로 글 1건. 없으면 여기서 즉시 404 로 끝난다(아래 줄은 실행되지 않음)
  post = Post.query.get_or_404(id)
  # 인가: 글쓴이 번호와 요청자 번호가 다르면 403. role 은 보지 않는다(admin 도 403)
  if post.author_id != user_id:
    return jsonify({'msg': '권한이 없습니다.'}), 403

  # 본문 읽기(없으면 {} → 아무것도 안 바뀐 채 commit 되어 200)
  data = request.get_json(silent=True) or {}
  # data.get('키', 기존값) : 키를 보냈으면 그 값, 안 보냈으면 기존 값 유지.
  #   빈 문자열·null 도 '보낸 값'이라 그대로 들어간다(함정 ④)
  post.title = data.get('title', post.title)
  post.content = data.get('content', post.content)
  post.category = data.get('category', post.category)
  # 바뀐 속성은 세션이 알아서 추적 → commit 때 UPDATE 실행 (add 가 필요 없다)
  db.session.commit()
  return jsonify({'msg': '수정되었습니다.'})


# ═════════════════════════════════════════════════════════════════════════════
# delete_post(id) — 글 삭제 (Delete) · 작성자 본인만
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 쪽지 떼기. 붙인 사람만 뗄 수 있다.
#
# 입력: 주소의 id(정수), 헤더 Authorization: Bearer <토큰>   (body 없음)
# 출력: 200 {"msg": "삭제되었습니다."}
#       401·422 토큰 문제 / 404 없는 글(HTML) / 403 남의 글
# 누가 호출하나: templates/index.html 의 deletePost() (확인 창에서 '확인')
# 주소: DELETE /api/posts/<id>
# ═════════════════════════════════════════════════════════════════════════════
@post_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_post(id):
  user_id = int(get_jwt_identity())
  # 없는 글이면 404
  post = Post.query.get_or_404(id)
  # 남의 글이면 403 — 수정과 같은 인가 규칙
  if post.author_id != user_id:
    return jsonify({'msg': '권한이 없습니다.'}), 403

  # DELETE 예약 → commit 으로 확정. 되돌리기(휴지통) 기능은 없다
  db.session.delete(post)
  db.session.commit()
  return jsonify({'msg': '삭제되었습니다.'})
