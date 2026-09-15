"""[주석·설명용 사본] models/post.py — 게시글 모델 (회원과 1:N 관계)

이 파일은 원본 models/post.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본 models/post.py 를 import 한다(models/__init__.py 경유).
    이 사본은 이름에 공백·하이픈이 있어 import 문으로 불러올 수 없다 — 읽기 전용 교재다.
  · 원본에는 모듈 설명이 없어 이 설명 문자열을 새로 붙였다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "게시글 한 편 = posts 표의 한 행. author_id 외래키로 '누가 썼는지(users.id)'를 가리키고,
   relationship 으로 post.author(작성자 객체) ⇄ user.posts(그 회원의 글 목록)를 오간다"

==============================================================================
1. 쉬운 비유 — 도서관의 '책'과 '회원 카드'
==============================================================================
  posts 표 / Post        = 서가의 책
  users 표 / User        = 회원 카드 보관함
  author_id(외래키)      = 책 안쪽에 적힌 '저자 회원번호' — 숫자일 뿐이다
  author(relationship)   = 사서에게 "이 번호 회원 카드 좀 가져다줘요" 하면 카드를 들고 오는 기능
  backref posts          = 반대로 회원 카드에서 "이 사람이 쓴 책 전부"를 찾아오는 기능
  lazy=True(지연 로딩)   = 사서는 '물어볼 때' 비로소 보관함에 다녀온다(미리 가져다 두지 않는다)

  책에는 회원번호(author_id)만 적어 두고 이름은 적지 않는다.
  이름이 필요하면(to_dict 의 'author') 그때 회원 카드를 가져와 읽는다.
  → 회원 정보가 한 곳(users)에만 있어 중복이 없지만, 목록을 만들 때 보관함 왕복이 생긴다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ ORM · 모델 클래스 · 대리키 id
      class Post(db.Model) ⇄ 표 posts. 객체 1개 = 행 1개.
      id = db.Column(db.Integer, primary_key=True) → MySQL AUTO_INCREMENT(1, 2, 3… 자동 번호).
      이 번호가 커서 페이지네이션(?cursor=)과 수정·삭제 주소(/api/posts/<id>)에 쓰인다.

  ■ nullable=False (필수 컬럼)
      title·content·category·author_id 모두 NOT NULL. 값 없이 INSERT 하면 DB 가 거절한다.

  ■ 외래키(Foreign Key) — db.ForeignKey('users.id')
      posts.author_id 의 값은 반드시 users 표의 id 중 하나여야 한다는 DB 규칙.
      MySQL(InnoDB)은 없는 회원 번호를 넣거나, 글이 남아 있는 회원을 SQL 로 지우는 것을 막는다.
      괄호 안 문자열은 '표이름.컬럼이름' 이다(클래스 이름 User 가 아니라 표 이름 users).

  ■ 1:N(일대다) 관계
      회원 1명 : 글 여러 편. 외래키는 '여러 개' 쪽인 posts 에 둔다.

  ■ relationship — 파이썬 쪽 연결(DB 컬럼이 생기지 않는다)
      author = db.relationship('User', ...)  →  post.author 가 User 객체를 돌려준다.
      괄호 안 'User' 는 '클래스 이름' 문자열. 실제 클래스는 나중(매퍼 설정 때)에 찾는다
      → 그래서 models/__init__.py 가 User 까지 모두 import 해 둬야 한다.

  ■ backref — 반대 방향 속성을 자동으로 만든다
      backref=db.backref('posts', lazy=True)  →  User 클래스에 user.posts(글 목록 list)가 생긴다.
      models/user.py 를 열어 봐도 posts 는 적혀 있지 않다 — 여기서 붙여 준 것이다.
      (현재 프로젝트 코드에서 user.posts 를 실제로 쓰는 곳은 없다)

  ■ lazy (로딩 시점)
      lazy=True 는 'select' 와 같다: 속성에 처음 접근할 때 SELECT 를 한 번 보낸다(지연 로딩).
      다른 값 예) 'joined'(처음 조회 때 JOIN 으로 함께), 'selectin'(IN 목록으로 한꺼번에).
      post.author 쪽은 lazy 를 따로 안 줬으므로 기본값 'select' — 역시 지연 로딩이다.

  ■ cascade (부모에게 한 일을 자식에게 전파하는 규칙)
      지정하지 않아 기본값 'save-update, merge'. 부모를 지울 때 자식도 지우는 'delete' 는 들어 있지 않다.

  ■ 인증과 소유자 검사
      글쓰기는 JWT 로그인 필요(@jwt_required). 토큰 안의 회원 번호가 author_id 로 들어가고,
      수정·삭제는 post.author_id 가 토큰의 회원 번호와 같을 때만 허용한다(다르면 403).

==============================================================================
3. 동작 원리
==============================================================================
  [글쓰기]  POST /api/posts  (헤더 Authorization: Bearer <토큰>)  post_controller.create_post
       │ user_id = int(get_jwt_identity())          ← 토큰에 담긴 회원 번호(users.id)
       │ Post(title, content, category=요청값 또는 '일반', author_id=user_id)
       │ db.session.add → commit   (이때 INSERT, id 가 매겨진다)
       ▼ 201 {"msg": "게시글이 등록되었습니다.", "id": 13}

  [목록]  GET /api/posts?cursor=&limit=5&search=&category=   post_controller.get_posts
       │ Post.query → category 필터('전체'면 생략) → title/content LIKE 검색 → id < cursor
       │ id 내림차순으로 limit+1 개 조회 (하나 더 가져와 has_more 판정)
       │ 글마다 to_dict()
       │     └ self.author 처음 접근 → SELECT ... FROM users WHERE users.id = <author_id>  (지연 로딩)
       ▼ {"posts": [to_dict(), ...], "next_cursor": ..., "has_more": ...}  → index.html 이 카드로 그림

  [골드 목록]  GET /api/gold/posts  (@role_required('gold'))   gold_controller.gold_posts
       │ Post.query.filter_by(category='골드') 최신 20개 → to_dict()
       ▼ {"count": n, "posts": [...]}  → gold.html

  [보안 공지 자동 등록]  POST /api/security/events 가 deny 이고 AUTO_POST_ON_DENY=1 이면
       │ security_controller._create_security_post → soarbot 계정 명의로 category='보안' 글을 추가

  [수정·삭제]  PUT·DELETE /api/posts/<id>
       │ Post.query.get_or_404(id) → post.author_id != 토큰의 회원 번호 → 403 "권한이 없습니다."

==============================================================================
4. 옵션 설명 — 컬럼·관계별
==============================================================================
  속성        파이썬 선언 → MySQL DDL                       옵션                         뜻 · 이 값을 준 이유
  ----------  --------------------------------------------  ---------------------------  --------------------------------------
  id          db.Integer                                    primary_key=True             글 번호(대리키). 자동 번호.
              → INTEGER NOT NULL AUTO_INCREMENT, PK                                      커서 페이지네이션·수정/삭제 주소에 쓰인다.
  title       db.String(200)                                nullable=False               제목. 목록 카드에 보이는 짧은 글이라 String.
              → VARCHAR(200) NOT NULL                                                    컨트롤러는 비었으면 400(길이는 자르지 않음).
  content     db.Text                                       nullable=False               본문. 길이를 예측할 수 없어 Text.
              → TEXT NOT NULL                                                            (MySQL TEXT 최대 65,535 바이트)
  category    db.String(50)                                 nullable=False,              분류: '일반'·'공지'·'골드'·'보안' 등 자유 문자열.
              → VARCHAR(50) NOT NULL                        default='일반'               값을 안 주면 INSERT 때 파이썬이 '일반'.
                                                                                         DDL 에는 DEFAULT 가 없다(파이썬 쪽 기본값).
  author_id   db.Integer, db.ForeignKey('users.id')         nullable=False               작성자 회원 번호. users.id 를 가리키는 외래키.
              → INTEGER NOT NULL,                                                        작성자 없는 글은 허용하지 않는다.
                FOREIGN KEY(author_id) REFERENCES users (id)
  author      db.relationship('User',                       backref, lazy                DB 컬럼 아님. post.author → User 객체(작성자).
              backref=db.backref('posts', lazy=True))                                    반대편 user.posts → 그 회원의 글 list 를 자동 생성.

  relationship 인자 풀이
    'User'                      : 연결할 클래스 이름(문자열). ForeignKey 의 'users.id'(표.컬럼)와 헷갈리지 말 것
    backref=db.backref(...)     : 반대 방향 속성을 만들고, 그 속성의 옵션을 따로 준다
      'posts'                   : User 에 생길 속성 이름
      lazy=True                 : user.posts 에 접근할 때 SELECT (= 'select')
    (지정 안 한 것들의 기본값)
      post.author 의 lazy       : 'select' (지연 로딩)
      cascade                   : 'save-update, merge' — 새 Post 를 세션에 add 하면 연결된 객체도 함께 저장 대상이 된다.
                                  'delete' 가 없으므로 회원을 지워도 글이 따라 지워지지 않는다
    옵션 용어
      primary_key / nullable    : 기본키 / NULL 허용 여부(안 적으면 기본키 제외 NULL 허용)
      default                   : INSERT 때 값이 비어 있으면 파이썬이 채움(DDL 에 안 나타남)
    (unique · index · server_default 는 이 모델에 없다)

==============================================================================
5. 예시
==============================================================================
  users 표                     posts 표
    id  username                 id  title            content      category  author_id
    1   lsy                      12  첫 글            안녕하세요   일반      1
    2   kim                      13  골드 회원 안내   ...          골드      2
                                 14  두 번째 글       ...          일반      1

  to_dict() 결과 — GET /api/posts 의 "posts", GET /api/gold/posts 의 "posts" 배열 원소
    {"id": 12, "title": "첫 글", "content": "안녕하세요", "category": "일반",
     "author": "lsy", "author_id": 1}
    'author' 는 posts 표에 없는 값이다 — to_dict() 가 users 표에서 가져온 아이디다.
    index.html 은 이 'author' 를 로그인 아이디와 비교해 '수정/삭제' 버튼을 보여 줄지 정한다.

  GET /api/posts?limit=2 응답
    {"posts": [{"id": 14, ...}, {"id": 13, ...}], "next_cursor": 13, "has_more": true}

  사용 코드
    post = Post(title='첫 글', content='안녕하세요', author_id=1)   # category 생략 → INSERT 때 '일반'
    post.author.username     # 'lsy' — 이 줄에서 users 조회 SELECT 가 나간다(지연 로딩)
    user.posts               # backref: 그 회원의 글 list — 접근할 때 SELECT

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 목록의 숨은 추가 조회(N+1). to_dict() 의 self.author.username 이 작성자를 지연 로딩하므로
     글 목록을 만들 때 '서로 다른 작성자 수'만큼 SELECT 가 더 나간다(같은 작성자는 세션이 기억해 다시 안 간다).
     글이 많아지면 쿼리에서 작성자를 함께 불러오는 방식(joined·selectin 로딩)을 검토한다.
  ② category 는 서버가 검사하지 않는 자유 문자열이다.
     · 로그인한 누구나 category='골드'·'보안' 으로 글을 쓸 수 있다 → 골드 전용 목록·보안 공지처럼 보이게 된다.
     · 일반 목록 GET /api/posts 는 등급 검사가 없고 '골드' 글을 빼지도 않는다
       → /api/posts?category=골드 로 로그인 없이 골드 글을 볼 수 있다(골드 전용 API 를 우회).
  ③ default='일반' 은 '값을 아예 안 줬을 때'만 쓰인다. 요청에 "category": "" 를 보내면
     컨트롤러가 빈 문자열을 그대로 넣어 빈 분류가 저장된다. DDL 에는 DEFAULT 가 없어 SQL 직접 INSERT 에도 안 먹는다.
  ④ 회원 삭제 주의(현재 코드에 회원 삭제 기능은 없다).
     ORM 으로 글이 있는 User 를 지우면 기본 cascade 에 delete 가 없어 SQLAlchemy 가 posts.author_id 를 NULL 로
     바꾸려 하고, nullable=False 에 막혀 에러가 난다. SQL 로 직접 지우면 MySQL 외래키가 막는다.
     테스트용 SQLite 는 기본 설정에서 외래키를 검사하지 않아 결과가 다를 수 있다.
  ⑤ ForeignKey 는 '표이름.컬럼'('users.id'), relationship 은 '클래스 이름'('User') — 반대로 쓰면 에러.
  ⑥ user.posts 는 user.py 에 보이지 않는다. backref 로 여기서 만들어지므로 "User 에 posts 가 어디 있지?" 하면 이 파일을 본다.
  ⑦ title 200자 제한은 DB 가 검사한다. 컨트롤러가 자르지 않으므로 더 긴 제목은 MySQL 엄격 모드(8.0 기본값)에서 에러,
     테스트용 SQLite 에서는 그대로 저장된다.
  ⑧ 화면의 '내 글' 판단(index.html)은 아이디 문자열 비교라 버튼 표시용일 뿐이다.
     실제 차단은 서버가 author_id 와 토큰의 회원 번호를 비교해서 한다(403).
"""
# ─────────────────────────────────────────────────────────────────────────────
# import — db : extensions.py 의 SQLAlchemy() 객체(모든 모델이 공유)
#   이 모델은 시각 컬럼이 없어 datetime 을 import 하지 않는다.
# ─────────────────────────────────────────────────────────────────────────────
from extensions import db


# ═════════════════════════════════════════════════════════════════════════════
# Post — 게시글 1편 = posts 표의 행 한 개
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 서가의 책 한 권. 안쪽에 '저자 회원번호(author_id)'만 적혀 있다.
# 입력: POST /api/posts 의 title·content·category + 토큰의 회원 번호(author_id)
# 출력: 표의 행 / to_dict() → /api/posts, /api/gold/posts 응답의 "posts" 배열
# 누가 쓰나: post_controller(CRUD), gold_controller(골드 목록),
#            security_controller(거부 이벤트 보안 공지 자동 등록), tests/test_rbac.py
# ═════════════════════════════════════════════════════════════════════════════
class Post(db.Model):
  # DB 안의 표 이름. SQL 로 확인할 때:  SELECT * FROM posts ORDER BY id DESC;
  __tablename__ = 'posts'

  # 글 번호(대리키). 정수 기본키 → MySQL AUTO_INCREMENT
  id = db.Column(db.Integer, primary_key=True)
  # 제목(필수). 짧은 글이라 길이 제한 있는 String(200) = VARCHAR(200)
  title = db.Column(db.String(200), nullable=False)
  # 본문(필수). 길이를 예측할 수 없어 Text = TEXT
  content = db.Column(db.Text, nullable=False)
  # 분류(필수). 값을 안 주면 INSERT 때 파이썬이 '일반'. DDL 에는 DEFAULT 가 안 들어간다.
  #   화면·API 가 쓰는 값 예: '일반', '공지'(index.html 이 빨간 배지), '골드'(골드 전용 목록), '보안'(자동 공지)
  category = db.Column(db.String(50), nullable=False, default='일반')
  # 작성자 회원 번호(필수). db.ForeignKey('users.id') = users 표의 id 컬럼을 가리키는 외래키.
  #   문자열은 '표이름.컬럼이름' 이다(클래스 이름 User 가 아님).
  author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
  # 관계(DB 컬럼 아님): post.author → 작성자 User 객체
  #   'User'                         : 연결할 '클래스 이름' 문자열(나중에 실제 클래스로 찾는다)
  #   backref=db.backref('posts', …) : 반대편 User 에 user.posts(글 list) 속성을 자동으로 만든다
  #   lazy=True                      : user.posts 에 접근할 때 SELECT 한다(= 'select', 지연 로딩)
  #   post.author 자체의 lazy·cascade 는 기본값('select' / 'save-update, merge')
  author = db.relationship('User', backref=db.backref('posts', lazy=True))

  # ═══════════════════════════════════════════════════════════════════════════
  # to_dict() — 글 1편을 JSON 으로 보낼 수 있는 dict 로
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: 책의 서지 카드를 만들면서, 저자 칸에는 회원 카드에서 이름을 가져와 적는다.
  # 입력: 없음(self)   출력: {'id', 'title', 'content', 'category', 'author', 'author_id'}
  # 누가 쓰나: post_controller.get_posts(GET /api/posts), gold_controller.gold_posts(GET /api/gold/posts)
  # ═══════════════════════════════════════════════════════════════════════════
  def to_dict(self):
    return {
        'id': self.id,
        'title': self.title,
        'content': self.content,
        'category': self.category,
        # 표에 없는 값: relationship 으로 작성자 User 를 불러와 아이디(username)만 꺼낸다.
        #   처음 접근할 때 users 조회 SELECT 가 나간다(지연 로딩).
        #   작성자를 못 찾으면(author 가 None) None.username 에서 AttributeError → 500.
        #   MySQL 은 외래키가 막아 주지만 외래키를 검사하지 않는 DB 에서는 생길 수 있다.
        'author': self.author.username,
        # 원래 컬럼 값(숫자). 화면·클라이언트가 회원 번호로 비교할 때 쓸 수 있다
        'author_id': self.author_id,
    }
