# alert_sender.py — 과제 1: 로그인 경보를 n8n Webhook 으로 전송하는 파이썬 전송기
"""
경보 목록을 만들어 n8n Webhook 으로 POST 한다.

실행:
    python alert_sender.py

기대 출력:
    [n8n] POST http://localhost:5678/webhook/... -> 200
"""
import sys

import requests  # pip install requests

# ── 설정: 본인 값으로 바꿀 것 ─────────────────────────────
STUDENT = "홍주형"  # 채점 증적 — 반드시 본인 식별자로 바꾼다
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/7e556d53-a1db-48d5-b35a-2a7dfff408b9"
TIMEOUT = 10  # 초

# 거부(레벨 10 이상)와 허용(레벨 10 미만)이 모두 섞이도록 구성한다.
# ip 는 예약 대역(1.2.3.x, 192.168.x.x)만 사용 — 실제 개인 서버로 보내지 않는다.
ALERTS = [
    {"ip": "1.2.3.114", "level": 10, "rule": "5712"},   # 레벨 10 -> 거부(High) 기대
    {"ip": "192.168.0.10", "level": 3, "rule": "5710"},  # 레벨 3  -> 허용(Low) 기대
]


def build_payload(student, alerts):
  return {"student": student, "alerts": alerts}


def send_to_n8n(url, payload):
  """n8n Webhook 으로 전송. 실패해도 프로그램이 죽지 않고 메시지만 출력한다."""
  try:
    res = requests.post(url, json=payload, timeout=TIMEOUT)
    print(f"[n8n] POST {url} -> {res.status_code}")
    if res.text:
      print(f"[n8n] response: {res.text[:300]}")
    return res.status_code
  except requests.RequestException as e:
    print(f"[n8n] 전송 실패: {e}", file=sys.stderr)
    return None


def main():
  payload = build_payload(STUDENT, ALERTS)
  print(f"[alert_sender] student={STUDENT} alerts={len(ALERTS)}건 전송 시도")
  status = send_to_n8n(N8N_WEBHOOK_URL, payload)
  if status is None:
    return 1
  return 0 if status == 200 else 1


if __name__ == "__main__":
  sys.exit(main())
