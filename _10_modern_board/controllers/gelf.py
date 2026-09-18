"""GELF 전송 헬퍼 — 게시판(앱)이 보안 로그를 Graylog(SIEM)로 직접 전송합니다.

GELF: JSON 포맷, UDP 12201 (fire-and-forget).
전송 실패는 비즈니스 로직(로그인 등)을 차단하지 않도록 안전하게 예외를 무시합니다.
"""
import json
import socket
from flask import current_app


def send_gelf(short_message, rule, **fields):
    """GELF 경보를 Graylog 로 전송합니다.
    short_message: 사람이 읽는 요약 메시지
    rule: `_rule` 값 (SIEM 필터링 키)
    **fields: 추가 메타데이터 (username, src_ip, count 등)
    """
    host = current_app.config.get('GELF_HOST', 'localhost')
    port = int(current_app.config.get('GELF_PORT', 12201))
    msg = {
        'version': '1.1',
        'host': 'board',
        'short_message': short_message,
        'level': 4,
        '_rule': rule
    }
    for k, v in fields.items():
        msg['_' + k] = v
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.sendto(json.dumps(msg).encode(), (host, port))
        finally:
            s.close()
    except Exception:
        pass  # SIEM 미작동 시에도 주 기능은 안전하게 동작
