"""공공데이터(부산 테마여행) 프록시 API."""
import requests
from flask import Blueprint, current_app, jsonify

from urllib.parse import unquote

public_bp = Blueprint('public', __name__, url_prefix='/api/public')


@public_bp.route('/posts', methods=['GET'])
def get_public_posts():
  raw_key = current_app.config.get('PUBLIC_API_KEY') or ''
  service_key = unquote(raw_key.strip())
  params = {
      'serviceKey': service_key,
      'numOfRows': '100',
      'pageNo': '1',
      'resultType': 'json',
  }
  try:
    res = requests.get(current_app.config['PUBLIC_API_URL'],
                       params=params, timeout=10)
    if res.status_code == 200:
      return res.json()
    return jsonify({'msg': '공공 API 호출 실패',
                    'status': res.status_code}), 500
  except requests.RequestException as e:
    return jsonify({'msg': '서버 통신 에러 발생', 'error': str(e)}), 500
