"""[주석·설명용 사본] controllers/public_controller.py — 공공데이터(부산 테마여행) 프록시 API

이 파일은 원본 controllers/public_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 import 한다(controllers/__init__.py 의 from .public_controller import public_bp).
    이 사본은 블루프린트로 등록되지 않는다. 파일 이름에 공백이 있어 import 문으로 부를 수도 없다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "브라우저 대신 우리 서버가 공공데이터포털(부산 테마여행 API)에 서비스키를 붙여
   대신 물어보고, 받은 JSON 을 손대지 않고 그대로 돌려주는 '심부름(프록시)' API"

==============================================================================
1. 쉬운 비유 — 호텔 안내 데스크
==============================================================================
  화면 JS (브라우저)              = 여행객
  이 API (GET /api/public/posts)  = 호텔 안내 데스크 직원
  공공데이터포털(부산 API)         = 시청 관광과
  서비스키(PUBLIC_API_KEY)        = 안내 데스크만 가진 관광과 출입증
  timeout=10                      = "10초 안에 답이 없으면 전화를 끊는다"
  응답 JSON                       = 관광과가 준 안내 책자(데스크는 펼쳐 보지도 않고 그대로 건넨다)

  여행객이 직접 관광과에 가려면 출입증(서비스키)을 들고 가야 한다.
  그런데 화면 JS 에 키를 넣으면 페이지 소스를 여는 누구에게나 키가 보인다.
  그래서 출입증은 데스크(서버)만 갖고, 여행객은 데스크에 "부산 여행지 알려주세요"라고만 한다.
  데스크는 관광과에 전화해 책자를 받아 그대로 건네고, 통화가 안 되면 "연락이 안 됩니다"라고 알린다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 프록시(Proxy) API
      클라이언트 요청을 받아 '다른 서버'에 대신 요청하고 결과를 전달하는 API.
      장점: 비밀 키를 서버에만 둔다 / 화면은 우리 서버 주소 하나만 알면 된다.

  ■ Blueprint 와 url_prefix
      블루프린트 = 관련 라우트를 묶은 '부서'. url_prefix='/api/public' 과
      라우트 '/posts' 가 합쳐져 최종 주소가 GET /api/public/posts 가 된다.
      app.py 가 controllers/__init__.py 의 all_blueprints 를 돌며 등록한다.

  ■ current_app.config
      '지금 요청을 처리 중인 앱'의 설정(dict 비슷한 것). config.py 의 Config 값이 들어 있다.
        config.get('이름')  : 없으면 None
        config['이름']      : 없으면 KeyError 예외
      이 파일은 키에는 .get(), 주소에는 [] 를 쓴다(주소는 config.py 에 항상 정의돼 있다).

  ■ requests.get(url, params=..., timeout=...)
      파이썬에서 HTTP GET 을 보내는 외부 라이브러리.
        params  : dict 를 주면 ?serviceKey=...&numOfRows=100... 쿼리스트링을 만들어 붙이고
                  URL 인코딩도 해 준다. 값이 None 인 항목은 쿼리에서 아예 빠진다.
        timeout : 초 단위. requests 는 기본 timeout 이 없어서 안 주면 응답이 올 때까지 계속 기다린다.

  ■ 서비스키(serviceKey)
      공공데이터포털(data.go.kr)에서 발급받은 인증키. .env.example 은
      '일반 인증키(Decoding)' 를 PUBLIC_API_KEY 에 넣으라고 안내한다(아래 함정 참고).

  ■ 예외 처리 — requests.RequestException
      requests 가 던지는 예외들의 부모 클래스. 연결 실패(ConnectionError), 시간초과(Timeout),
      그리고 설치된 requests 2.34.2 기준으로 res.json() 의 JSON 해석 실패(JSONDecodeError)까지
      모두 이 부모를 상속하므로 except 한 줄로 함께 잡힌다.

  ■ HTTP 상태코드
      200 = 성공,  500 = 서버 내부 오류.
      이 API 는 외부 API 쪽 문제도 전부 500 으로 돌려준다.
      (의미를 더 정확히 나누면 502 Bad Gateway / 504 Gateway Timeout 을 쓰기도 한다)

  ■ Flask 에서 dict 반환
      Flask 3.0 은 뷰 함수가 dict(또는 list)를 return 하면 자동으로 JSON 응답(200)으로 만든다.
      그래서 res.json() 결과(dict)를 jsonify 없이 바로 return 해도 된다.

==============================================================================
3. 동작 원리 — 요청에서 응답까지
==============================================================================

   [public_posts.html / public_detail.html 의 JS]
        │  fetch('/api/public/posts')
        ▼
   [get_public_posts]
        │ ① params 준비: serviceKey=설정값, numOfRows=100, pageNo=1, resultType=json
        │ ② requests.get(PUBLIC_API_URL, params, timeout=10)
        ▼
   [공공데이터포털  apis.data.go.kr  (부산 RecommendedService/getRecommendedKr)]
        │
        ▼
     ③ 결과 판정
        · 응답 코드 200                     → res.json() 을 그대로 반환 (200)
        · 응답 코드가 200 이 아님            → {"msg": "공공 API 호출 실패", "status": 원래코드} (500)
        · 연결 실패 / 10초 초과 / JSON 아님  → {"msg": "서버 통신 에러 발생", "error": 에러문구} (500)
        ▼
   [화면 JS]  data.getRecommendedKr?.item 배열을 꺼낸다
        · public_posts.html  : 카드 목록(썸네일·제목·설명). 클릭하면 /public-posts/<UC_SEQ>
        · public_detail.html : 같은 API 를 다시 불러 UC_SEQ 가 일치하는 1건을 찾아 상세 표시
        · 배열이 비어 있으면(500 응답 포함) "조회된 데이터가 없습니다. 인증키를 확인해주세요."

==============================================================================
4. 옵션 설명
==============================================================================
  ■ 엔드포인트
    | 메서드 | URL               | 인증       | 쿼리 파라미터 | body | 응답 코드 |
    |--------|-------------------|------------|---------------|------|-----------|
    | GET    | /api/public/posts | 없음(누구나) | 없음(붙여도 무시) | 없음 | 200 / 500 |

    화면 주소(page_controller.py)와 헷갈리지 말 것:
      /public-posts            → 목록 화면(HTML)
      /public-posts/<uc_seq>   → 상세 화면(HTML)
      /api/public/posts        → 이 파일의 데이터 API(JSON)

  ■ 블루프린트·라우트 인자
    | 코드                                  | 뜻                                              |
    |---------------------------------------|-------------------------------------------------|
    | Blueprint('public', ...)              | 블루프린트 이름. 엔드포인트 이름이 public.get_public_posts 가 된다 |
    | Blueprint(..., __name__)              | 이 모듈의 import 이름(템플릿·정적파일 위치 계산용) |
    | url_prefix='/api/public'              | 이 블루프린트 모든 주소 앞에 붙는 공통 경로      |
    | @public_bp.route('/posts', methods=['GET']) | GET 요청만 받는다(POST 등은 405)          |

  ■ 사용하는 설정값 (config.py)
    | 설정            | 어디서 오나                        | 없을 때                           |
    |-----------------|------------------------------------|-----------------------------------|
    | PUBLIC_API_KEY  | .env 의 PUBLIC_API_KEY             | None → serviceKey 가 쿼리에서 빠짐 |
    | PUBLIC_API_URL  | config.py 에 고정된 문자열          | 항상 있음(환경변수로 못 바꾼다)     |
      PUBLIC_API_URL = http://apis.data.go.kr/6260000/RecommendedService/getRecommendedKr
      (tests/test_rbac.py 의 TestConfig 는 이 값을 http://example.invalid/ 로 바꿔 쓴다)

  ■ 외부 API 에 보내는 요청 파라미터 (params)
    | 이름        | 값                 | 의미                        |
    |-------------|--------------------|-----------------------------|
    | serviceKey  | PUBLIC_API_KEY     | 공공데이터포털 인증키         |
    | numOfRows   | '100'              | 한 번에 받을 건수            |
    | pageNo      | '1'                | 페이지 번호(항상 1쪽만)       |
    | resultType  | 'json'             | 응답 형식을 JSON 으로 요청    |

  ■ requests.get 인자
    | 인자      | 값                  | 설명                                   |
    |-----------|---------------------|----------------------------------------|
    | url       | PUBLIC_API_URL      | 부를 주소                              |
    | params    | 위 dict             | 쿼리스트링으로 변환(None 값은 제외)       |
    | timeout   | 10                  | 숫자 하나면 연결·응답 읽기 각각에 10초 적용 |

==============================================================================
5. 요청·응답 예시
==============================================================================
    curl http://localhost:5000/api/public/posts

  성공 (200) — 제공처 JSON 그대로. 화면 JS 가 읽는 부분만 줄여 쓰면(templates 기준):
    {"getRecommendedKr": {"item": [
        {"UC_SEQ": 58, "TITLE": "...", "MAIN_IMG_THUMB": "https://...",
         "MAIN_IMG_NORMAL": "https://...", "ITEMCNTNTS": "..."},
        ...]}}

  제공처가 200 이 아닌 코드를 준 경우 (500)
    {"msg": "공공 API 호출 실패", "status": 401}        ← status 는 제공처가 준 원래 코드(예시 값)

  연결 실패·시간초과·JSON 해석 실패 (500)
    {"msg": "서버 통신 에러 발생",
     "error": "... Max retries exceeded with url: /6260000/RecommendedService/getRecommendedKr?serviceKey=<PUBLIC_API_KEY>&numOfRows=100&pageNo=1&resultType=json (Caused by ...)"}
    ↑ 연결 실패일 때의 모양. 시간초과·JSON 오류는 문구가 다르다.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 에러 응답에 서비스키가 새어 나갈 수 있다.
     연결 실패 예외 문구(str(e))에는 요청 경로와 쿼리스트링이 들어 있고, 쿼리에는 serviceKey 가 있다.
     이 API 는 인증이 없으므로 그 문구가 누구의 브라우저로든 그대로 간다(위 5절 예시).
     실서비스라면 에러 상세는 서버 로그에만 남기고 응답에는 일반 문구만 준다.
  ② PUBLIC_API_KEY 를 비워 두면 serviceKey 파라미터 자체가 빠진 채로 요청된다(requests 가 None 을 제외).
     서버는 에러를 내지 않고 제공처 응답을 그대로 판정하므로, 화면에는 결국
     "조회된 데이터가 없습니다. 인증키를 확인해주세요." 가 보이기 쉽다.
  ③ 키는 Decoding(일반) 키를 넣는다. requests 가 params 를 다시 URL 인코딩하므로
     이미 인코딩된(Encoding) 키를 넣으면 % 가 %25 로 한 번 더 바뀌어 다른 키가 된다.
  ④ 제공처가 200 을 주더라도 본문이 JSON 이 아니면 res.json() 이 실패해 500 "서버 통신 에러 발생" 이 된다.
     반대로 200 + JSON 이면 내용이 무엇이든 그대로 200 으로 전달된다 — 이 파일은 내용을 검사하지 않는다.
  ⑤ 받은 데이터는 '외부에서 온 HTML/문자열'이다. 이 API 는 걸러내지 않으므로 화면이 조심해야 한다.
     public_detail.html 은 ITEMCNTNTS 를 innerHTML 에 그대로 넣고, public_posts.html 도 TITLE 을
     이스케이프 없이 넣는다(제공처 데이터에 스크립트가 섞이면 XSS 위험).
  ⑥ 요청마다 외부 API 를 새로 부른다(캐시 없음). 상세 화면도 목록 100건 전체를 다시 받아 찾으므로
     100건 밖의 항목은 찾지 못한다. 그때 public_detail.html 은 id="container" 요소를 찾는데
     그런 id 가 없어(class 만 container) 안내 문구 대신 JS 오류가 난다.
     또 인증이 없어 누구나 이 주소를 반복 호출할 수 있고, 그만큼 서버가 외부 API 를 부른다.
  ⑦ PUBLIC_API_URL 은 http(평문)다. 서비스키가 암호화되지 않은 채 쿼리스트링에 실려 간다.
  ⑧ 주소 오타 주의: /api/public-posts 는 없는 주소라 404 다(tests/test_public_api.py 4번이 확인).
     templates 의 '-수정으로확인용' 사본들이 이 틀린 주소를 부른다.
  ⑨ tests/test_public_api.py 는 실제 app.py 를 import 한다 → .env 의 DB 와 실제 공공 API 에 접속한다.
     외부 상태에 따라 200 이든 500 이든 둘 다 통과로 본다(응답에 msg 또는 getRecommendedKr 키만 확인).
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
#   requests       : 외부 서버에 HTTP 요청을 보내는 라이브러리(pip 설치 필요)
#   Blueprint      : 라우트 묶음(부서) 만들기
#   current_app    : 지금 요청을 처리 중인 앱 — 설정(config)을 꺼낼 때 쓴다
#   jsonify        : dict → JSON 응답 객체 (상태코드를 함께 돌려줄 때 편하다)
# ─────────────────────────────────────────────────────────────────────────────
import requests
from flask import Blueprint, current_app, jsonify

# 블루프린트 생성: 이름 'public', 모든 주소 앞에 /api/public 이 붙는다.
#   controllers/__init__.py 가 이 public_bp 를 all_blueprints 에 넣고, app.py 가 등록한다.
public_bp = Blueprint('public', __name__, url_prefix='/api/public')


# ═════════════════════════════════════════════════════════════════════════════
# get_public_posts() — 부산 테마여행 목록을 공공데이터포털에서 대신 받아 온다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 안내 데스크 직원이 출입증(서비스키)을 들고 관광과에 전화해 책자 100쪽을 받아 오는 일.
#
# 입력: 없음 (쿼리 파라미터·body 를 읽지 않는다)
# 출력: 200 → 제공처 JSON 그대로
#       500 → {"msg": "공공 API 호출 실패", "status": 제공처 코드}
#       500 → {"msg": "서버 통신 에러 발생", "error": 예외 문구}
#
# 누가 호출하나: templates/public_posts.html (목록), templates/public_detail.html (상세)
#               tests/test_public_api.py (실제 호출 테스트)
# 주소: GET /api/public/posts   (url_prefix '/api/public' + '/posts')
# ═════════════════════════════════════════════════════════════════════════════
@public_bp.route('/posts', methods=['GET'])
def get_public_posts():
  # ── ① 외부 API 에 붙일 쿼리 파라미터 ──
  # requests 가 이 dict 를 ?serviceKey=...&numOfRows=100&pageNo=1&resultType=json 으로 바꿔 붙인다.
  # 값은 문자열로 적었지만 숫자로 줘도 requests 가 문자열로 바꿔 보낸다.
  params = {
      # 인증키. .env 에 없으면 None → requests 가 이 항목을 쿼리에서 빼 버린다(에러 없음)
      'serviceKey': current_app.config.get('PUBLIC_API_KEY'),
      # 한 번에 100건 (화면 제목의 "최대 100건" 이 여기서 온다)
      'numOfRows': '100',
      # 항상 1페이지만 받는다 → 100건을 넘는 데이터는 이 API 로는 볼 수 없다
      'pageNo': '1',
      # 응답을 XML 이 아니라 JSON 으로 달라고 요청
      'resultType': 'json',
  }
  # ── ② 외부 호출 — 네트워크는 언제든 실패할 수 있으니 try 로 감싼다 ──
  try:
    # PUBLIC_API_URL 은 config.py 에 항상 정의돼 있으므로 [] 로 꺼낸다(없으면 KeyError).
    # timeout=10 : 연결·응답 읽기 각각 10초 안에 안 되면 requests.Timeout 예외.
    #   timeout 을 빼면 제공처가 멈췄을 때 이 요청을 처리하는 서버 쪽도 계속 붙잡혀 있게 된다.
    res = requests.get(current_app.config['PUBLIC_API_URL'],
                       params=params, timeout=10)
    # ── ③ 결과 판정 ──
    # 제공처가 200(성공)을 주면
    if res.status_code == 200:
      # 응답 본문(JSON 문자열) → dict. Flask 가 dict 를 다시 JSON 응답(200)으로 만들어 준다.
      # 본문이 JSON 이 아니면 여기서 JSONDecodeError → 아래 except 로 간다(RequestException 의 자식).
      return res.json()
    # 200 이 아니면(키 오류·서버 점검 등) 원래 코드를 status 에 담아 알려주고, 우리 응답은 500
    return jsonify({'msg': '공공 API 호출 실패',
                    'status': res.status_code}), 500
  # 연결 거부, DNS 실패, 10초 초과, JSON 해석 실패 등을 한 번에 잡는다
  except requests.RequestException as e:
    # str(e) : 예외 문구를 그대로 응답에 싣는다.
    # 주의(함정 ①): 연결 실패 문구에는 serviceKey 가 들어간 요청 경로가 포함된다.
    return jsonify({'msg': '서버 통신 에러 발생', 'error': str(e)}), 500
