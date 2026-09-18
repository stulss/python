"""공공데이터 프록시 및 부산 테마여행 API 컨트롤러

엔드포인트:
  · /api/public/posts  : _7_board_test 호환 공공 API 호출 프록시
  · /api/openapi       : 부산 테마여행 정보 서비스 Open API 연동
"""
from urllib.parse import unquote
import requests
from flask import Blueprint, current_app, jsonify, request
from routes.openapi import openapi_bp

public_bp = Blueprint('public', __name__, url_prefix='/api/public')


@public_bp.route('/posts', methods=['GET'])
def get_public_posts():
    """_7_board_test 호환 공공 API 프록시"""
    raw_key = current_app.config.get('PUBLIC_API_KEY') or ''
    service_key = unquote(raw_key.strip())
    api_url = current_app.config.get('PUBLIC_API_URL', 'http://apis.data.go.kr/6260000/RecommendedService/getRecommendedKr')

    params = {
        'serviceKey': service_key,
        'numOfRows': request.args.get('numOfRows', '100'),
        'pageNo': request.args.get('pageNo', '1'),
        'resultType': 'json',
    }
    try:
        res = requests.get(api_url, params=params, timeout=10)
        if res.status_code == 200:
            return res.json()
        return jsonify({'msg': '공공 API 호출 실패', 'status': res.status_code}), 500
    except requests.RequestException as e:
        return jsonify({'msg': '서버 통신 에러 발생', 'error': str(e)}), 500
