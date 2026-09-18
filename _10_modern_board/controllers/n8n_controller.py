"""n8n SOAR 자동화 연동 컨트롤러 (/api/n8n)

'모던커뮤니티 보안관제' 워크플로우 (ID: OdFvNv9vWoqt7Hqg)와 완벽히 결합합니다.
워크플로우 구조:
  1. Webhook (/webhook/c0ab8317-528d-4a1f-a354-2719862ce37f)
  2. JavaScript 판정 로직 (level >= 10: deny/High, level >= 7: allow/Medium, else: allow/Low)
  3. Discord, Slack, Telegram 다중 알림 전송
  4. 게시판 REST API (http://host.docker.internal:5000/api/security/events) 자동 저장
"""
import json
import requests
from flask import Blueprint, request, jsonify, current_app
from config import Config
from .rbac import role_required

n8n_bp = Blueprint('n8n', __name__, url_prefix='/api/n8n')

MODERN_SECURITY_WF_ID = 'OdFvNv9vWoqt7Hqg'
MODERN_REVOKE_WF_ID = 'SY02H3Ra4jjLkX4d'


def _get_n8n_headers():
    api_key = current_app.config.get('N8N_API_KEY', '')
    return {
        'X-N8N-API-KEY': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


@n8n_bp.route('/status', methods=['GET'])
@role_required('gold')
def get_n8n_status():
    """n8n 연결 상태 및 모던커뮤니티 보안관제 워크플로우 상태 반환"""
    base_url = current_app.config.get('N8N_BASE_URL', 'http://localhost:5678/api/v1')
    headers = _get_n8n_headers()

    try:
        res = requests.get(f"{base_url}/workflows", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json().get('data', [])
            workflows = [{
                'id': w.get('id'),
                'name': w.get('name'),
                'active': w.get('active'),
                'is_target': (w.get('id') == MODERN_SECURITY_WF_ID),
                'createdAt': w.get('createdAt'),
                'updatedAt': w.get('updatedAt')
            } for w in data]

            # 모던커뮤니티 보안관제 워크플로우 찾기
            sec_wf = next((w for w in workflows if w['id'] == MODERN_SECURITY_WF_ID), None)

            return jsonify({
                'connected': True,
                'status': 'HEALTHY',
                'n8n_url': 'http://localhost:5678',
                'target_workflow': sec_wf,
                'workflow_count': len(workflows),
                'workflows': workflows
            }), 200
        else:
            return jsonify({
                'connected': False,
                'status': 'AUTH_OR_API_ERROR',
                'error': f'n8n API 응답 오류 (코드: {res.status_code})',
                'details': res.text
            }), 502
    except Exception as e:
        return jsonify({
            'connected': False,
            'status': 'DISCONNECTED',
            'error': f'n8n 서버에 연결할 수 없습니다: {str(e)}'
        }), 503


@n8n_bp.route('/trigger', methods=['POST'])
@role_required('gold')
def trigger_n8n_webhook():
    """모던커뮤니티 보안관제 워크플로우 웹훅으로 이벤트 발송 (골드/관리자)"""
    data = request.get_json(silent=True) or {}
    webhook_type = data.get('type', 'security')  # 'security' or 'revoke'

    if webhook_type == 'revoke':
        webhook_url = current_app.config.get('N8N_WEBHOOK_URL_REVOKE')
        payload = data
    else:
        # 모던커뮤니티 보안관제 워크플로우 Webhook
        webhook_url = current_app.config.get('N8N_WEBHOOK_URL_SECURITY')

        # n8n 'Code in JavaScript' 노드가 요구하는 포맷(student, alerts: [{ip, level, rule}]) 생성
        student = data.get('student', '모던커뮤니티_보안팀')
        src_ip = data.get('src_ip', request.remote_addr or '203.0.113.100')
        level = int(data.get('level', 12))  # 10 이상: deny, 7~9: allow/Medium, <7: allow/Low
        rule = data.get('rule', 'BRUTE_FORCE_1001')

        # 직접 alerts 배열이 전달된 경우 그대로 사용, 아니면 단일 alert 래핑
        if 'alerts' in data and isinstance(data['alerts'], list):
            payload = {
                'student': student,
                'alerts': data['alerts']
            }
        else:
            payload = {
                'student': student,
                'alerts': [
                    {
                        'ip': src_ip,
                        'level': level,
                        'rule': rule
                    }
                ]
            }

    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        return jsonify({
            'success': True,
            'message': f'모던커뮤니티 보안관제 n8n 워크플로우로 이벤트가 성공적으로 발송되었습니다.',
            'webhook_url': webhook_url,
            'sent_payload': payload,
            'n8n_status_code': res.status_code,
            'n8n_response': res.text[:200]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'n8n 웹훅 호출 실패: {str(e)}',
            'webhook_url': webhook_url
        }), 500


@n8n_bp.route('/run-revoke-bot', methods=['POST'])
@role_required('admin')
def run_revoke_bot():
    """이상 권한 자동 탐지 및 회수 봇(privilege_revoke_bot.py) 즉시 실행 (관리자 전용)"""
    import subprocess
    import sys

    try:
        proc = subprocess.run(
            [sys.executable, '-u', 'privilege_revoke_bot.py'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        return jsonify({
            'success': True,
            'message': '이상권한 자동 탐지 및 회수 봇 실행 완료',
            'output': proc.stdout,
            'stderr': proc.stderr
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f'봇 실행 실패: {str(e)}'}), 500


@n8n_bp.route('/workflows/<string:wf_id>/activate', methods=['POST'])
@role_required('admin')
def activate_workflow(wf_id):
    """n8n 워크플로우 활성화"""
    base_url = current_app.config.get('N8N_BASE_URL', 'http://localhost:5678/api/v1')
    headers = _get_n8n_headers()

    try:
        res = requests.post(f"{base_url}/workflows/{wf_id}/activate", headers=headers, json={}, timeout=5)
        if res.status_code in (200, 201):
            return jsonify({'success': True, 'message': f'워크플로우 {wf_id}가 활성화되었습니다.'}), 200
        return jsonify({'success': False, 'error': res.text}), res.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
