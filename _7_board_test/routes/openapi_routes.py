from datetime import datetime
import logging
import requests
from config import Config
from db import get_db_connection
from flask import Blueprint, jsonify, request

openapi_bp = Blueprint("openapi", __name__, url_prefix="/api/openapi")
logger = logging.getLogger(__name__)

# [문서 기준 공식 URL] 부산광역시_부산테마여행정보서비스 Open API 엔드포인트
BUSAN_THEME_API_URL = "http://apis.data.go.kr/6260000/RecommendedService/getRecommendedKr"

BUSAN_GUGUNS = [
    "전체",
    "해운대구",
    "수영구",
    "영도구",
    "중구",
    "서구",
    "사하구",
    "기장군",
    "남구",
    "부산진구",
    "동래구",
    "금정구",
    "강서구",
    "북구",
    "사상구",
    "동구"
]

# 중복 없는 고유한 100대 부산 테마여행지 마스터 데이터셋
UNIQUE_100_BUSAN_THEMES = [
    # 1. 해운대구 (10개)
    ("해운대 블루라인파크 & 스카이캡슐", "해운대구", "부산광역시 해운대구 청사포로 116", "해안 절경을 달리는 해변열차와 스카이캡슐 코스", "https://images.unsplash.com/photo-1596422846543-75c6fc197f07?w=600", "09:30 ~ 19:00", "해변열차 7,000원~", "051-701-5548", "https://www.bluelinepark.com"),
    ("해운대 해수욕장 & 송림공원", "해운대구", "부산광역시 해운대구 해운대해변로 264", "대한민국 대표 해수욕장과 울창한 솔숲 해변 산책로", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "24시간 상시 개방", "무료", "051-749-5700", "https://www.haeundae.go.kr"),
    ("동백섬 & 누리마루 APEC하우스", "해운대구", "부산광역시 해운대구 동백로 116", "동백꽃 숲길과 APEC 정상회담이 열린 아름다운 해안 명소", "https://images.unsplash.com/photo-1548115184-bc6544d06a58?w=600", "09:00 ~ 17:00", "무료", "051-743-1947", "https://www.visitbusan.net"),
    ("청사포 다릿돌전망대 & 쌍둥이등대", "해운대구", "부산광역시 해운대구 중동 산3-9", "바다 위로 뻗은 스릴 넘치는 투명 유리 전망대와 조개구이 거리", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", "09:00 ~ 18:00", "무료", "051-749-5700", "https://www.haeundae.go.kr"),
    ("달맞이길 & 문탠로드", "해운대구", "부산광역시 해운대구 달맞이길 190", "부산의 몽마르트르 언덕으로 불리는 감성 갤러리와 벚꽃길", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "24시간 상시 개방", "무료", "051-749-4000", "https://www.haeundae.go.kr"),
    ("부산 엑스더스카이 (LCT 100층 전망대)", "해운대구", "부산광역시 해운대구 달맞이길 30", "국내 2위 초고층 건물에서 내려다보는 해운대 360도 파노라마 뷰", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600", "10:00 ~ 21:00", "대인 27,000원", "051-731-0098", "http://www.busanxthesky.com"),
    ("영화의전당 & 센텀시티", "해운대구", "부산광역시 해운대구 수영강변대로 120", "부산국제영화제(BIFF) 전용관과 거대한 빅루프 야경 명소", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", "09:00 ~ 22:00", "시설별 상이", "051-780-6000", "http://www.dureraum.org"),
    ("신세계 센텀시티 스파랜드", "해운대구", "부산광역시 해운대구 센텀남대로 35", "천연 온천수를 즐길 수 있는 세계 최고 수준의 도심형 웰니스 휴양지", "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=600", "09:00 ~ 22:00", "대인 23,000원", "1668-2850", "https://www.shinsegae.com"),
    ("해운대 전통시장 & 구남로 문화광장", "해운대구", "부산광역시 해운대구 구남로41번길 22-1", "상국이네 떡볶이와 곰장어 골목, 버스킹이 펼쳐지는 보행자 특화거리", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "09:00 ~ 22:00", "무료", "051-746-3001", "https://www.visitbusan.net"),
    ("송정 해수욕장 & 서핑빌리지", "해운대구", "부산광역시 해운대구 송정해변로 62", "사계절 파도가 좋아 서퍼들의 성지로 불리는 액티비티 천국", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=600", "24시간 상시 개방", "무료", "051-749-5800", "https://www.haeundae.go.kr"),

    # 2. 수영구 (7개)
    ("광안리 M 드론 라이트쇼 & 해수욕장", "수영구", "부산광역시 수영구 광안해변로 219", "광안대교 야경과 매주 토요일 펼쳐지는 상설 드론 라이트쇼", "https://images.unsplash.com/photo-1548115184-bc6544d06a58?w=600", "상시 (드론쇼 토요일 밤)", "무료", "051-610-4882", "https://www.suyeong.go.kr/drone"),
    ("민락수변공원 & 민락더마켓", "수영구", "부산광역시 수영구 민락수변로 17-1", "바다를 품은 복합문화공간과 로컬 푸드, 오션뷰 플리마켓", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "10:00 ~ 24:00", "무료", "051-752-5678", "http://millacmarket.kr"),
    ("F1963 복합문화공간 & YES24 서점", "수영구", "부산광역시 수영구 구락로123번길 20", "옛 와이어 공장이 전시장, 도서관, 감성 카페 테라로사로 재탄생한 공간", "https://images.unsplash.com/photo-1507842229451-79b1be897a20?w=600", "09:00 ~ 21:00", "무료 (전시별 상이)", "051-756-1963", "http://www.f1963.org"),
    ("남천동 빵천동 골목 & 벚꽃거리", "수영구", "부산광역시 수영구 남천동 일원", "전국 유명 베이커리가 밀집한 디저트 성지와 봄철 벚꽃 터널", "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600", "상점별 상이", "무료", "051-610-4000", "https://www.suyeong.go.kr"),
    ("수영사적공원 & 안용복장군 사당", "수영구", "부산광역시 수영구 수영성로 43", "조선시대 경상좌도 수군절도사영 터와 울릉도·독도를 지킨 역사 유적지", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "24시간 상시 개방", "무료", "051-610-4882", "https://www.suyeong.go.kr"),
    ("망미골목 감성 카페 & 독립서점 투어", "수영구", "부산광역시 수영구 망미배산로 일원", "예술가들의 작은 공방과 골목 갤러리들이 모여있는 핫플레이스", "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600", "11:00 ~ 20:00", "무료", "051-610-4000", "https://www.visitbusan.net"),
    ("광안리 해양레포츠센터 패들보드(SUP)", "수영구", "부산광역시 수영구 광안해변로54번길 22", "광안대교를 배경으로 즐기는 일출·일몰 SUP 패들보드 체험", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=600", "09:00 ~ 18:00", "체험비 30,000원~", "051-622-0027", "https://www.suyeongsup.kr"),

    # 3. 영도구 (8개)
    ("흰여울문화마을 해안절벽 산책로", "영도구", "부산광역시 영도구 절영로 194", "해안 절벽 위 하얀 집들과 푸른 남항 바다가 어우러진 영화 '변호인' 촬영지", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", "24시간 상시 개방", "무료", "051-419-4067", "https://www.yeongdo.go.kr"),
    ("태종대 유원지 & 다누비열차", "영도구", "부산광역시 영도구 전망로 24", "울창한 숲과 기암절벽, 영도등대 전망대에서 대마도까지 조망하는 명소", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "05:00 ~ 24:00 (열차 09:20~)", "입장 무료 (열차 4,000원)", "051-405-8745", "http://www.taejongdae.or.kr"),
    ("피아크(P.ARK) 복합문화공간 & 오션가든", "영도구", "부산광역시 영도구 해양로 195", "선박 모양의 초대형 건축물에서 즐기는 커피와 파노라마 오션뷰 테라스", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600", "10:00 ~ 23:00", "무료", "051-404-9200", "http://p-ark.kr"),
    ("깡깡이예술마을 & 도선체험", "영도구", "부산광역시 영도구 대평북로 36", "우리나라 최초의 근대식 조선소가 있던 마을로 예술 벽화와 선박 도선 체험", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", "10:00 ~ 17:00", "체험비 별도", "051-418-1863", "http://kangkangee.com"),
    ("국립해양박물관", "영도구", "부산광역시 영도구 해양로301번길 45", "대형 원통형 수족관과 해양 문화·역사를 한눈에 보는 국내 최대 해양박물관", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-309-1900", "https://www.knmm.or.kr"),
    ("영도 해녀촌 & 중리노을전망대", "영도구", "부산광역시 영도구 중리북로 2-35", "해녀들이 갓 잡아 올린 성게알 김밥과 황홀한 붉은 노을 뷰", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "09:00 ~ 19:00", "식사비 별도", "051-419-4000", "https://www.visitbusan.net"),
    ("삼진어묵 본점 & 영도 어묵역사체험관", "영도구", "부산광역시 영도구 태종로99번길 36", "1953년부터 시작된 국내 최고(最古) 어묵 브랜드 본점과 수제어묵 만들기 체험", "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600", "09:00 ~ 19:00", "체험 15,000원", "051-412-5468", "https://www.samjinfood.com"),
    ("봉래산 & 조내기 고구마 역사기념관", "영도구", "부산광역시 영도구 벚꽃길 75", "영도 한가운데 솟은 봉래산 정상에서 바라보는 부산항 360도 전경", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "09:00 ~ 18:00", "무료", "051-419-4091", "https://www.yeongdo.go.kr"),

    # 4. 중구 (8개)
    ("자갈치시장 & 신동아수산물종합시장", "중구", "부산광역시 중구 자갈치해안로 52", "'오이소! 보이소! 사이소!' 활기찬 부산 어시장의 싱싱한 회와 꼼장어", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "05:00 ~ 22:00", "무료입장", "051-713-8000", "http://jagalchimarket.kr"),
    ("용두산공원 & 부산타워(다이아몬드타워)", "중구", "부산광역시 중구 용두산길 37-55", "부산 원도심과 북항 바다를 한눈에 조망하는 부산 1호 랜드마크 타워", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600", "10:00 ~ 22:00", "전망대 12,000원", "051-661-9393", "http://bisco.or.kr"),
    ("국제시장 & 609 청년몰", "중구", "부산광역시 중구 신창동4가", "영화 '국제시장'의 무대이자 만물 상설 시장과 개성 있는 청년 창업 공간", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "09:00 ~ 20:00", "무료", "051-245-7389", "http://www.gukjemarket.co.kr"),
    ("부평 깡통시장 & 야시장 먹거리 골목", "중구", "부산광역시 중구 부평1길 48", "비빔당면, 유부전골, 씨앗호떡, 세계 야시장 야식의 천국", "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600", "19:30 ~ 23:30 (야시장)", "무료입장", "051-243-1128", "http://www.kkangtong.com"),
    ("보수동 책방골목 & 문화관", "중구", "부산광역시 중구 책방골목길 8", "6.25 전쟁 피란 시절부터 이어져 온 70년 전통의 고서와 헌책 골목", "https://images.unsplash.com/photo-1507842229451-79b1be897a20?w=600", "10:00 ~ 19:00", "무료", "051-241-5036", "http://www.bosubook.com"),
    ("40계단 문화관광테마거리", "중구", "부산광역시 중구 40계단길", "피란민의 애환과 향수가 서려 있는 1950년대 근현대사 테마거리", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "24시간 상시 개방", "무료", "051-600-4041", "http://www.bsjunggu.go.kr"),
    ("부산근현대역사관 (구 동양척식주식회사)", "중구", "부산광역시 중구 대청로 112", "일제강점기 근대 건축물에 조성된 부산의 개항과 현대사 복합문화공간", "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-607-8000", "https://museum.busan.go.kr"),
    ("영도대교 도개 행사 관람스팟", "중구", "부산광역시 중구 중앙동7가", "매주 토요일 오후 2시 다리 상판이 75도 각도로 번쩍 들리는 역사적 도개교", "https://images.unsplash.com/photo-1548115184-bc6544d06a58?w=600", "매주 토 14:00 (15분간)", "무료", "051-600-4000", "http://www.bsjunggu.go.kr"),

    # 5. 서구 (6개)
    ("송도 해상케이블카 & 송도스카이파크", "서구", "부산광역시 서구 송도해변로 171", "바다 위 86m 상공을 가로지르는 1.62km 크리스탈 캐빈 해상 케이블카", "https://images.unsplash.com/photo-1596422846543-75c6fc197f07?w=600", "09:00 ~ 21:00", "왕복 17,000원~", "051-247-9900", "http://busanaircruise.co.kr"),
    ("송도 용궁구름다리 & 암남공원", "서구", "부산광역시 서구 암남공원로 127", "암남공원에서 동섬을 연결하는 아찔한 바다 위 철망 교량", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "09:00 ~ 18:00", "입장료 1,000원", "051-240-4087", "https://www.bsseogu.go.kr"),
    ("송도 구름산책로 & 거북섬 인어공주상", "서구", "부산광역시 서구 송도해변로 100", "365m 길이로 바다 위를 걷는 곡선형 스카이워크 산책로", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", "06:00 ~ 23:00", "무료", "051-240-4082", "https://www.bsseogu.go.kr"),
    ("송도 해수욕장 & 오토캠핑장", "서구", "부산광역시 서구 송도해변로 100", "1913년 개장한 대한민국 제1호 공설 해수욕장과 캠핑 스팟", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=600", "24시간 개방", "무료", "051-240-4000", "https://www.bsseogu.go.kr"),
    ("임시수도기념관 & 대통령관저", "서구", "부산광역시 서구 임시수도기념로 45", "한국전쟁 당시 이승만 대통령 관저와 임시정부 국무총리 집무실", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-244-6345", "https://museum.busan.go.kr/monument"),
    ("천마산 하늘전망대 & 모노레일", "서구", "부산광역시 서구 천마산로 107", "부산 원도심 야경과 부산항 대교를 가장 높은 파노라마로 감상하는 뷰포인트", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "24시간 상시 개방", "무료", "051-240-4000", "https://www.bsseogu.go.kr"),

    # 6. 사하구 (7개)
    ("감천문화마을 아트투어 & 어린왕자 포토존", "사하구", "부산광역시 사하구 감내2로 203", "한국의 산토리니로 불리는 계단식 주택 골목 벽화마을", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", "09:00 ~ 18:00", "무료", "051-204-1444", "https://www.gamcheon.or.kr"),
    ("다대포 꿈의 낙조분수 & 음악분수쇼", "사하구", "부산광역시 사하구 몰운대1길 14", "세계 최대 바닥 음악분수로 기네스북에 등재된 화려한 조명 분수쇼", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600", "20:00 분수쇼 (하절기)", "무료", "051-220-5891", "https://www.saha.go.kr/fountain"),
    ("다대포 고우니 생태길 (갈대밭 데크)", "사하구", "부산광역시 사하구 다대동 1572", "황금빛 갈대밭 사이로 붉게 물드는 부산 최고 일몰 명소", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "24시간 상시 개방", "무료", "051-220-4000", "https://www.saha.go.kr"),
    ("몰운대 해안둘레길 & 자갈마당", "사하구", "부산광역시 사하구 다대동 산144", "안개와 구름에 잠겨 보이지 않는다 하여 붙여진 울창한 숲과 절벽 산책로", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "05:00 ~ 20:00", "무료", "051-220-4081", "https://www.saha.go.kr"),
    ("을숙도 철새도래지 & 에코센터", "사하구", "부산광역시 사하구 낙동남로 1240", "낙동강 하구 천혜의 삼각주 생태계와 겨울 철새들의 보금자리", "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600", "09:00 ~ 18:00", "무료", "051-209-2000", "http://www.busan.go.kr/wetland"),
    ("부산현대미술관 (MoCA Busan)", "사하구", "부산광역시 사하구 낙동남로 1191", "수직정원 외관과 뉴미디어 현대미술 기획전시가 열리는 공공 미술관", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", "10:00 ~ 18:00 (월 휴관)", "무료 (일부 유료)", "051-220-7400", "http://www.busan.go.kr/moca"),
    ("아미산전망대 & 모래톱 전시관", "사하구", "부산광역시 사하구 다대낙조2길 77", "낙동강과 바다가 만나는 삼각주 모래톱과 서해 낙조를 조망하는 건축 명소", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "09:00 ~ 18:00", "무료", "051-265-6863", "http://www.busan.go.kr/wetland"),

    # 7. 기장군 (9개)
    ("기장 해동용궁사 바다사찰", "기장군", "부산광역시 기장군 기장읍 용궁길 86", "동해 푸른 바다 기암절벽 위에 세워진 일출 명소 사찰", "https://images.unsplash.com/photo-1548115184-bc6544d06a58?w=600", "04:30 ~ 19:20", "무료입장", "051-722-7744", "http://www.yongkungsa.or.kr"),
    ("기장 아홉산숲 대나무 숲길", "기장군", "부산광역시 기장군 철마면 미동길 37-1", "남평 문씨 일가가 400년간 가꿔온 비밀의 대나무 숲 (영화 군도 촬영지)", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "09:00 ~ 18:00", "입장료 5,000원", "051-721-9183", "http://www.ahopsan.com"),
    ("롯데월드 어드벤처 부산 & 오시리아", "기장군", "부산광역시 기장군 기장읍 동부산관광로 42", "동화 속 왕국 테마파크와 자이언트디거 롤러코스터 테마 어트랙션", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600", "10:00 ~ 20:00", "종일권 47,000원", "1661-2000", "https://adventurebusan.lotteworld.com"),
    ("국립부산과학관 & 천체투영관", "기장군", "부산광역시 기장군 기장읍 동부산관광6로 59", "탑승형 우주선 체험과 과학 원리를 배우는 동남권 거점 과학관", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600", "09:30 ~ 17:30 (월 휴관)", "상설전시 3,000원", "051-750-2300", "https://www.sciport.or.kr"),
    ("기장 연화리 해녀촌 & 전복죽 포장마차", "기장군", "부산광역시 기장군 기장읍 연화1길 169", "바다 앞에서 가마솥 전복죽과 싱싱한 해산물 모둠을 맛보는 명소", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "09:00 ~ 18:00", "식사비 별도", "051-709-4000", "https://www.gijang.go.kr"),
    ("대변항 & 기장 멸치 축제거리", "기장군", "부산광역시 기장군 기장읍 대변리", "은빛 멸치털이 장관과 기장 미역·다시마 특산물 항구", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "상시 개방", "무료", "051-709-4000", "https://www.gijang.go.kr"),
    ("죽성드림세트장 (죽성성당) & 두호마을", "기장군", "부산광역시 기장군 기장읍 죽성리 134-7", "드라마 '드림' 세트장으로 바다 절벽 위 이국적인 풍경의 출사 성지", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", "24시간 상시 개방", "무료", "051-709-4000", "https://www.gijang.go.kr"),
    ("일광 해수욕장 & 학리항 찐빵거리", "기장군", "부산광역시 기장군 일광읍 삼성리", "수심이 얕고 모래가 고운 가족 휴양지와 유명 호빵·손만두 골목", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=600", "24시간 상시 개방", "무료", "051-709-4000", "https://www.gijang.go.kr"),
    ("장안사 계곡 & 척판암 고찰", "기장군", "부산광역시 기장군 장안읍 장안로 482", "신라 문무왕 때 원효대사가 창건한 천년 고찰과 단풍 숲길", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "07:00 ~ 18:00", "무료", "051-727-2393", "http://www.jangan.sa.kr"),

    # 8. 남구 (7개)
    ("오륙도 스카이워크 & 해맞이공원", "남구", "부산광역시 남구 오륙도로 137", "동해와 남해의 분기점으로 투명 유리 바닥 위에서 바라보는 오륙도 비경", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "09:00 ~ 18:00", "무료입장", "051-607-6395", "https://www.bsnamgu.go.kr"),
    ("이기대 수변공원 & 치마바위 트레킹", "남구", "부산광역시 남구 이기대공원로 105-20", "광안대교와 마린시티를 조망하며 걷는 해안 절벽 갈맷길 코스", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", "24시간 상시 개방", "무료", "051-607-6361", "https://www.bsnamgu.go.kr"),
    ("재한유엔기념공원 & 평화공원", "남구", "부산광역시 남구 유엔평화로 93", "세계 유일의 유엔군 전몰장병 안장 묘지이자 평화의 성지", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "09:00 ~ 17:00", "무료", "051-625-0625", "https://www.unmck.or.kr"),
    ("국립일제강제동원역사관", "남구", "부산광역시 남구 홍곡로 320", "일제강점기 강제동원의 아픈 역사와 추모 공간을 담은 국가 역사관", "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600", "10:00 ~ 18:00 (월 휴관)", "무료", "051-629-8600", "https://museum.fomo.or.kr"),
    ("부산시립박물관 & 문화회관", "남구", "부산광역시 남구 유엔평화로 63", "구석기시대부터 근현대까지 부산의 역사 유물을 전시하는 대표 박물관", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-610-7111", "https://museum.busan.go.kr"),
    ("신선대 부두 & 무제등 전망대", "남구", "부산광역시 남구 신선대산길 55", "화려한 컨테이너 부두 야경과 부산항 대교 조망 포인트", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "24시간 상시 개방", "무료", "051-607-4000", "https://www.bsnamgu.go.kr"),
    ("백운포 체육공원 & 오션뷰 낚시터", "남구", "부산광역시 남구 백운포로 110", "바다를 끼고 축구장, 풋살장, 해안 산책로가 조성된 종합 체육공원", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=600", "상시 개방", "무료", "051-607-4000", "https://www.bsnamgu.go.kr"),

    # 9. 부산진구 (8개)
    ("전포 카페거리 & 소품샵 골목", "부산진구", "부산광역시 부산진구 전포대로 209번길", "뉴욕타임스 추천 명소! 공구상가 골목에 탄생한 개성 만점 카페촌", "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=600", "11:00 ~ 22:00", "무료", "051-605-4522", "https://www.bsjin.go.kr"),
    ("부산시민공원 & 하야리아 잔디광장", "부산진구", "부산광역시 부산진구 시민공원로 73", "옛 미군기지가 울창한 도심 숲, 분수쇼, 피크닉 공원으로 재탄생한 공간", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "05:00 ~ 24:00", "무료", "051-850-6000", "http://www.citizenpark.or.kr"),
    ("황령산 봉수대 & 쉼터 전망대", "부산진구", "부산광역시 부산진구 황령산로 391-39", "부산 도심 360도 전경과 광안대교 야경을 가장 높은 곳에서 내려다보는 명소", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "24시간 상시 개방", "무료", "051-605-4000", "https://www.bsjin.go.kr"),
    ("서면 1번가 & 젊음의 거리", "부산진구", "부산광역시 부산진구 중앙대로691번길 42", "부산 최대 번화가로 쇼핑몰, 클럽, 맛집이 24시간 불야성을 이루는 거리", "https://images.unsplash.com/photo-1548115184-bc6544d06a58?w=600", "24시간 개방", "무료", "051-605-4000", "https://www.bsjin.go.kr"),
    ("송상현광장 & 도심 잔디스퀘어", "부산진구", "부산광역시 부산진구 동평로 115", "임진왜란 충절의 상징 송상현 동상과 시민들의 도심 문화 광장", "https://images.unsplash.com/photo-1507842229451-79b1be897a20?w=600", "24시간 상시 개방", "무료", "051-850-6000", "http://www.songpark.kr"),
    ("서면시장 돼지국밥 & 손칼국수 골목", "부산진구", "부산광역시 부산진구 서면로 56", "진한 사골 국물의 부산 명물 돼지국밥과 쫄깃한 시장 칼국수 맛집 골목", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "24시간 영업 (식당별)", "식사비 별도", "051-804-0098", "https://www.visitbusan.net"),
    ("삼광사 & 부처님오신날 연등축제", "부산진구", "부산광역시 부산진구 초읍천로43번길 77", "CNN 선정 한국 아름다운 명소로 수만 개의 오색 연등이 장관을 이루는 사찰", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "04:00 ~ 22:00", "무료입장", "051-808-7111", "http://www.samkwangsa.or.kr"),
    ("어린이대공원 & 성지곡수원지 편백숲", "부산진구", "부산광역시 부산진구 새싹로 295", "100년 된 삼나무와 편백나무 숲길 산책로와 맑은 호수 공원", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "05:00 ~ 23:00", "무료입장", "051-860-7848", "http://www.bisco.or.kr"),

    # 10. 동래구 (6개)
    ("동래온천 & 허심청 대온천탕", "동래구", "부산광역시 동래구 온천장로107번길 32", "신라시대부터 유명한 알칼리 온천수와 동양 최대 규모 웰니스 휴양지", "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=600", "05:30 ~ 22:00", "대인 15,000원", "051-550-2200", "http://www.hotelnongshim.com"),
    ("동래읍성지 & 북문광장 성곽길", "동래구", "부산광역시 동래구 명륜동 산1-1", "임진왜란 동래성 전투의 격전지 성곽을 따라 걷는 역사 산책로", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "24시간 상시 개방", "무료", "051-550-4082", "https://www.dongnae.go.kr"),
    ("복천동 고분군 & 복천박물관", "동래구", "부산광역시 동래구 복천로 63", "가야시대 지배층 무덤군과 철의 왕국 가야 유물을 한눈에 보는 야외 박물관", "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-554-4263", "https://museum.busan.go.kr/bokcheon"),
    ("금강공원 케이블카 & 로프웨이", "동래구", "부산광역시 동래구 우장춘로 155", "금정산 능선을 따라 케이블카를 타고 부산 시가지를 감상하는 코스", "https://images.unsplash.com/photo-1596422846543-75c6fc197f07?w=600", "09:30 ~ 17:30", "대인 왕복 11,000원", "051-552-1762", "http://geumgangpark.bisco.or.kr"),
    ("온천천 시민공원 & 벚꽃 카페거리", "동래구", "부산광역시 동래구 온천천로 일원", "봄철 화려한 벚꽃과 유채꽃, 개천을 따라 조성된 감성 브런치 카페거리", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "24시간 개방", "무료", "051-550-4000", "https://www.dongnae.go.kr"),
    ("동래파전 골목 & 동래별장", "동래구", "부산광역시 동래구 온천장로107번길 일원", "조선시대 임금님 진상품이었던 쪽파와 해물이 듬뿍 들어간 원조 동래파전", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "11:30 ~ 21:00", "식사비 별도", "051-552-3091", "https://www.dongnae.go.kr"),

    # 11. 금정구 (7개)
    ("금정산성 & 금샘 트레킹 코스", "금정구", "부산광역시 금정구 금정산성로", "국내 최장 18.8km 산성으로 사계절 등산객이 찾는 부산의 진산", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "24시간 상시 개방", "무료", "051-519-4081", "https://www.geumjeong.go.kr"),
    ("범어사 & 템플스테이 사찰투어", "금정구", "부산광역시 금정구 범어사로 250", "신라 문무왕 때 의상대사가 창건한 영남 3대 사찰과 맑은 대나무 숲", "https://images.unsplash.com/photo-1548115184-bc6544d06a58?w=600", "08:30 ~ 17:30", "무료입장", "051-508-3122", "http://www.beomeo.kr"),
    ("금정산성 막걸리마을 & 오리불고기촌", "금정구", "부산광역시 금정구 산성로 520", "대한민국 민속주 1호 쌀누룩 막걸리와 숯불 흑염소·오리 불고기 명소", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "10:00 ~ 21:00", "식음료비 별도", "051-517-0220", "https://www.geumjeong.go.kr"),
    ("회동수원지 & 땅뫼산 황토숲길", "금정구", "부산광역시 금정구 오륜대로 일원", "호수를 끼고 맨발로 걷는 힐링 황토길과 편백림 삼림욕장", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "24시간 상시 개방", "무료", "051-519-4081", "https://www.geumjeong.go.kr"),
    ("부산대학교 젊음의 거리 & 패션스트리트", "금정구", "부산광역시 금정구 부산대학로", "젊은 대학생들의 낭만과 저렴한 가성비 맛집, 패션 의류 상점가", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600", "상시 개방", "무료", "051-519-4000", "https://www.geumjeong.go.kr"),
    ("스포원파크 (금정체육공원) & 워터파크", "금정구", "부산광역시 금정구 체육공원로399번길 325", "가족 자전거 타기, 실내 수영장, 경륜 경기장 등을 갖춘 웰빙 복합공원", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600", "09:00 ~ 18:00", "입장 무료 (체육시설 유료)", "1577-0880", "http://www.spo1.or.kr"),
    ("오륜대 아홉산 회동호 둘레길", "금정구", "부산광역시 금정구 오륜동", "기암절벽과 호수가 만들어내는 한 폭의 동양화 같은 수변 둘레길", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", "24시간 개방", "무료", "051-519-4000", "https://www.geumjeong.go.kr"),

    # 12. 강서구 (6개)
    ("가덕도 대항항 포진지 동굴 & 외양포", "강서구", "부산광역시 강서구 대항동 산13-24", "일제강점기 군사 요새 포진지 동굴을 미디어아트로 단장한 역사 다크투어", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", "10:00 ~ 20:00", "무료", "051-970-4081", "https://www.bsgangseo.go.kr"),
    ("가덕도 연대봉 & 해안 절경 둘레길", "강서구", "부산광역시 강서구 천성동", "가덕도 최고봉(459m)에서 바라보는 거가대교와 남해 다도해 뷰", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "24시간 상시 개방", "무료", "051-970-4000", "https://www.bsgangseo.go.kr"),
    ("렛츠런파크 부산경남 & 일루미아 빛축제", "강서구", "부산광역시 강서구 가락대로 929", "사계절 펼쳐지는 화려한 빛의 마법 일루미아 조명과 경마 테마파크", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600", "18:00 ~ 24:00 (빛축제)", "대인 12,000원", "051-253-6666", "http://www.illumia.info"),
    ("명지 오션시티 해안산책로 & 철새탐조대", "강서구", "부산광역시 강서구 명지오션시티", "낙동강 하구 바다를 따라 길게 뻗은 자전거길과 해넘이 산책로", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=600", "24시간 상시 개방", "무료", "051-970-4000", "https://www.bsgangseo.go.kr"),
    ("대저생태공원 & 전국 최대 유채꽃단지", "강서구", "부산광역시 강서구 대저1동 2314-11", "봄철 23만 평 규모의 황금빛 유채꽃 축제와 핑크뮬리 정원", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "06:00 ~ 21:00", "무료", "051-970-4000", "https://www.busan.go.kr/nakdong"),
    ("맥도생태공원 & 벚꽃터널 자전거길", "강서구", "부산광역시 강서구 대저2동", "낙동강변을 따라 끝없이 펼쳐지는 벚꽃 터널과 연꽃 생태습지", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "06:00 ~ 21:00", "무료", "051-970-4000", "https://www.busan.go.kr/nakdong"),

    # 13. 북구 (5개)
    ("화명생태공원 & 야외 수영장/연꽃단지", "북구", "부산광역시 북구 화명동 1718-17", "낙동강변 드넓은 잔디광장과 수상레포츠 타운, 연꽃 습지", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600", "06:00 ~ 21:00", "무료", "051-309-4081", "https://www.busan.go.kr/nakdong"),
    ("화명수목원 & 초록 숲속 치유길", "북구", "부산광역시 북구 산성로 299", "금정산 계곡을 따라 1,300여 종의 식물과 유리온실이 있는 도심 수목원", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-362-0121", "http://forest.busan.go.kr"),
    ("구포시장 전통 5일장 & 구포국수거리", "북구", "부산광역시 북구 구포시장1길 6", "400년 역사를 자랑하는 부산 최대 상설 전통시장과 원조 쫄깃한 구포국수", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "08:00 ~ 20:00 (3,8일 오일장)", "무료입장", "051-333-3004", "http://www.gupomarket.or.kr"),
    ("부산어촌민속관 & 낙동강 역사체험", "북구", "부산광역시 북구 학사로 128", "낙동강 어촌의 삶과 물고기 전시를 체험하는 어린이 친화 박물관", "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600", "09:00 ~ 18:00 (월 휴관)", "무료", "051-550-8882", "https://museum.busan.go.kr/fish"),
    ("만덕 레고마을 & 만덕고개 야경 누리길", "북구", "부산광역시 북구 만덕동 일원", "알록달록한 지붕이 레고 블록처럼 모여있는 이색 마을과 만덕령 야경", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", "24시간 개방", "무료", "051-309-4000", "https://www.bsbukgu.go.kr"),

    # 14. 사상구 (5개)
    ("삼락생태공원 & 벚꽃축제 오토캠핑장", "사상구", "부산광역시 사상구 삼락동 29-46", "전국에서 가장 긴 벚꽃길과 오토캠핑장, 철새 먹이터가 있는 거대 생태공원", "https://images.unsplash.com/photo-1448375240586-882707db888b?w=600", "06:00 ~ 21:00", "무료 (캠핑장 유료)", "051-309-4000", "https://www.busan.go.kr/nakdong"),
    ("사상인디스테이션 (CATs 컨테이너 아트)", "사상구", "부산광역시 사상구 광장로 80", "선박 컨테이너를 쌓아 만든 청년 인디 문화예술 공연 복합공간", "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600", "10:00 ~ 19:00", "무료", "051-316-7630", "https://www.bscf.or.kr"),
    ("운수사 & 백양산 숲속 천년고찰", "사상구", "부산광역시 사상구 모라로192번길 80", "가야시대 창건 전설이 깃든 부산 최고(最古) 목조건물 대웅전(보물)", "https://images.unsplash.com/photo-1528728329032-2972f65dfb3f?w=600", "07:00 ~ 18:00", "무료", "051-317-5670", "https://www.sasang.go.kr"),
    ("사상 명품 가로공원 & 괘법 르네시떼", "사상구", "부산광역시 사상구 사상로 일원", "도시철도 사상역 주변 보행자 쉼터와 쇼핑몰 연계 도심 테마거리", "https://images.unsplash.com/photo-1507842229451-79b1be897a20?w=600", "24시간 개방", "무료", "051-310-4000", "https://www.sasang.go.kr"),
    ("삼락 수상레포츠 타운 (윈드서핑)", "사상구", "부산광역시 사상구 삼락동", "낙동강의 시원한 강바람을 맞으며 즐기는 윈드서핑과 카약 체험장", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=600", "09:00 ~ 18:00 (하절기)", "체험비 별도", "051-309-4000", "https://www.sasang.go.kr"),

    # 15. 동구 (6개)
    ("초량 이바구길 & 168계단 모노레일", "동구", "부산광역시 동구 영초위길 22", "산복도로 언덕을 오르는 경사형 모노레일과 피란민의 역사를 담은 이야기길", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", "07:00 ~ 20:00 (모노레일)", "무료", "051-440-4000", "http://www.bsdonggu.go.kr"),
    ("유치진문화관 & 명란로드 테마관", "동구", "부산광역시 동구 초량상로 49", "대한민국 명란젓의 발원지 초량 이바구길 명란 브랜드 체험관", "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600", "10:00 ~ 18:00", "무료", "051-440-4000", "http://www.bsdonggu.go.kr"),
    ("부산 차이나타운 특구 & 신발원 만두거리", "동구", "부산광역시 동구 대영로243번길 3", "화교 140년 전통의 정통 만두와 중국 전통 패루가 있는 이색 거리", "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "상점별 상이", "무료", "051-440-4000", "https://www.visitbusan.net"),
    ("부산역 유라시아 플랫폼 & 워터스크린", "동구", "부산광역시 동구 중앙대로 210", "부산의 관문 부산역 광장에 조성된 스타트업 및 복합 문화 광장", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600", "24시간 개방", "무료", "051-711-0050", "https://www.beplatform.or.kr"),
    ("산복도로 친환경 스카이웨이 전망대", "동구", "부산광역시 동구 망양로 533-1", "부산항 북항 바다와 원도심 전경을 한눈에 내려다보는 공중 데크 쉼터", "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=600", "24시간 상시 개방", "무료", "051-440-4000", "http://www.bsdonggu.go.kr"),
    ("초량 불백거리 & 원조 기사식당", "동구", "부산광역시 동구 초량로 34", "매콤달콤한 돼지불고기 백반으로 50년간 사랑받아온 기사식당 맛집 거리", "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600", "24시간 영업 (식당별)", "식사비 별도", "051-440-4000", "https://www.visitbusan.net")
]


def deduplicate_items(items):
    """제목 및 명소명 기준으로 중복을 엄격히 제거하는 함수"""
    seen = set()
    unique_items = []
    for item in items:
        # 제목에서 특수문자/숫자를 제외한 핵심 명소명 추출
        raw_title = item.get("title", "")
        clean_key = raw_title.replace("[", "").replace("]", "").split("#")[0].strip()
        if clean_key and clean_key not in seen:
            seen.add(clean_key)
            unique_items.append(item)
    return unique_items


def get_unique_mock_theme_data(count=100, gugun="전체"):
    """중복 없이 100% 고유한 부산 100선 명소 데이터 반환"""
    target_data = UNIQUE_100_BUSAN_THEMES
    if gugun != "전체":
        target_data = [t for t in UNIQUE_100_BUSAN_THEMES if t[1] == gugun]
        if not target_data:
            target_data = UNIQUE_100_BUSAN_THEMES

    items = []
    for idx, (title, g_name, addr, contents, img, utime, fee, tel, hp) in enumerate(target_data, start=1):
        items.append({
            "id": idx,
            "title": f"[{g_name}] {title}",
            "gugun": g_name,
            "addr": addr,
            "contents": contents,
            "imageUrl": img,
            "usageTime": utime,
            "fee": fee,
            "tel": tel,
            "homepage": hp,
            "isMock": True,
        })
        if len(items) >= count:
            break

    return items


@openapi_bp.route("/busan-themes", methods=["GET"])
def get_busan_themes():
    """
    부산 테마여행정보 100선 조회 REST API (중복 엄격 배제)
    Query Params:
        - numOfRows: 조회 건수 (기본값: 100, 최대 100)
        - gugun: 구군 필터 (기본값: '전체')
        - search: 검색어
    """
    num_of_rows = min(request.args.get("numOfRows", default=100, type=int), 100)
    gugun_filter = request.args.get("gugun", default="전체", type=str).strip()
    search = request.args.get("search", default="", type=str).strip()
    service_key = Config.OPENAPI_SERVICE_KEY

    # 키가 기본 템플릿이거나 미입력 상태면 고유 100선 데이터 반환
    if not service_key or "YOUR_PUBLIC_DATA" in service_key or "여기에" in service_key:
        items = get_unique_mock_theme_data(count=num_of_rows, gugun=gugun_filter)
        if search:
            items = [
                x for x in items
                if search in x["title"] or search in x["contents"] or search in x["addr"]
            ]

        return jsonify({
            "success": True,
            "source": "BUSAN_THEME_UNIQUE_100 (.env에 OPENAPI_SERVICE_KEY 등록 시 공공데이터포털 실시간 연동)",
            "totalCount": len(items),
            "items": items,
            "gugunList": BUSAN_GUGUNS,
        })

    # 실제 공공데이터포털 OPEN API 호출
    from urllib.parse import unquote
    clean_service_key = unquote(service_key.strip())

    params = {
        "serviceKey": clean_service_key,
        "resultType": "json",
        "numOfRows": num_of_rows,
        "pageNo": 1,
    }

    try:
        response = requests.get(BUSAN_THEME_API_URL, params=params, timeout=6)
        response.encoding = "utf-8"

        # XML 응답이거나 오류일 때 Fallback 제공
        if response.text.strip().startswith("<"):
            logger.warning(f"공공데이터포털 XML 응답: {response.text[:200]}")
            items = get_unique_mock_theme_data(count=num_of_rows, gugun=gugun_filter)
            return jsonify({
                "success": True,
                "source": "FALLBACK_DATA (공공데이터 키 동기화 대기 중 - 중복 없는 고유 100선 제공)",
                "totalCount": len(items),
                "items": items,
                "gugunList": BUSAN_GUGUNS,
            })

        data = response.json()
        body = []
        if isinstance(data, dict):
            if "getRecommendedKr" in data:
                tk = data["getRecommendedKr"]
                body = tk.get("item", []) or tk.get("items", {}).get("item", [])
            elif "getThemeKr" in data:
                tk = data["getThemeKr"]
                body = tk.get("item", []) or tk.get("items", {}).get("item", [])
            elif "response" in data:
                resp = data["response"]
                body = resp.get("body", {}).get("items", {}).get("item", []) or resp.get("body", {}).get("items", [])
            elif "items" in data:
                body = data.get("items", [])

        if isinstance(body, dict):
            body = [body]

        if not body:
            items = get_unique_mock_theme_data(count=num_of_rows, gugun=gugun_filter)
            return jsonify({
                "success": True,
                "source": "FALLBACK_DATA (공공데이터 응답 없음 - 중복 없는 고유 100선 제공)",
                "totalCount": len(items),
                "items": items,
                "gugunList": BUSAN_GUGUNS,
            })

        formatted_items = []
        for idx, item in enumerate(body, start=1):
            raw_title = item.get("MAIN_TITLE") or item.get("TITLE") or f"부산 명소 #{idx}"
            # "(한,영,중간,중번,일)" 같은 불필요한 다국어 표기 제거
            clean_title = raw_title.split("(")[0].strip() if "(" in raw_title else raw_title

            formatted_items.append({
                "id": idx,
                "title": clean_title,
                "rawTitle": raw_title,
                "subTitle": item.get("SUBTITLE") or item.get("TITLE", ""),
                "gugun": item.get("GUGUN_NM", "부산"),
                "category": item.get("CATE2_NM", "테마여행"),
                "place": item.get("PLACE", ""),
                "addr": item.get("ADDR1", "부산광역시 일원"),
                "contents": item.get("ITEMCNTNTS", "부산의 매력적인 테마여행 코스입니다."),
                "imageUrl": item.get(
                    "MAIN_IMG_NORMAL",
                    item.get(
                        "MAIN_IMG_THUMB",
                        "https://images.unsplash.com/photo-1596422846543-75c6fc197f07?w=600",
                    ),
                ),
                "traffic": item.get("TRFC_INFO", ""),
                "usageTime": item.get("USAGE_DAY_WEEK_AND_TIME") or item.get("USAGE_DAY", "상시 운영"),
                "fee": item.get("USAGE_AMOUNT", "무료 또는 개별 상이"),
                "tel": item.get("CNTCT_TEL", "051-1330"),
                "homepage": item.get("HOMEPAGE_URL", "https://www.visitbusan.net"),
                "isMock": False,
            })

        # 공공 API에서 가져온 항목들도 중복 제거 적용
        formatted_items = deduplicate_items(formatted_items)

        # 필터 적용
        if gugun_filter != "전체":
            formatted_items = [x for x in formatted_items if gugun_filter in x["gugun"]]
        if search:
            formatted_items = [
                x for x in formatted_items
                if search in x["title"] or search in x["contents"] or search in x["addr"]
            ]

        return jsonify({
            "success": True,
            "source": "REAL_DATA.GO.KR (부산광역시 부산테마여행정보 실시간)",
            "totalCount": len(formatted_items),
            "items": formatted_items,
            "gugunList": BUSAN_GUGUNS,
        })

    except Exception as e:
        logger.warning(f"부산 테마여행 API 오류 -> Fallback: {e}")
        items = get_unique_mock_theme_data(count=num_of_rows, gugun=gugun_filter)
        return jsonify({
            "success": True,
            "source": f"FALLBACK_DATA (오류로 인한 고유 100선 샘플 제공: {str(e)})",
            "totalCount": len(items),
            "items": items,
            "gugunList": BUSAN_GUGUNS,
        })


@openapi_bp.route("/save-to-db", methods=["POST"])
def save_themes_to_mysql():
    """조회된 부산 테마여행 데이터를 MySQL DB에 저장/동기화 (중복 방지 INSERT IGNORE)"""
    req_data = request.get_json() or {}
    items = req_data.get("items", [])

    if not items:
        return jsonify({"success": False, "message": "저장할 데이터가 없습니다."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS busan_theme_travel (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL UNIQUE,
                    gugun VARCHAR(50) NOT NULL,
                    addr VARCHAR(255),
                    contents TEXT,
                    image_url VARCHAR(500),
                    usage_time VARCHAR(100),
                    fee VARCHAR(100),
                    tel VARCHAR(50),
                    homepage VARCHAR(255),
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_gugun (gugun),
                    INDEX idx_title (title)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            sql = """
                INSERT INTO busan_theme_travel 
                (title, gugun, addr, contents, image_url, usage_time, fee, tel, homepage)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                addr=VALUES(addr), contents=VALUES(contents), image_url=VALUES(image_url),
                usage_time=VALUES(usage_time), fee=VALUES(fee), tel=VALUES(tel), homepage=VALUES(homepage);
            """
            rows = [
                (
                    item.get("title", ""),
                    item.get("gugun", ""),
                    item.get("addr", ""),
                    item.get("contents", ""),
                    item.get("imageUrl", ""),
                    item.get("usageTime", ""),
                    item.get("fee", ""),
                    item.get("tel", ""),
                    item.get("homepage", ""),
                )
                for item in items
            ]
            cursor.executemany(sql, rows)
            conn.commit()

            return jsonify({
                "success": True,
                "message": f"부산 테마여행지 {len(rows)}건이 MySQL 'busan_theme_travel' 테이블에 중복 없이 성공적으로 저장되었습니다!",
            })
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"DB 저장 오류: {str(e)}"}), 500
    finally:
        conn.close()
