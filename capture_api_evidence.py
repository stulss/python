"""터미널 캡처용 보안 이벤트 API 검증기.

사용법:
    python capture_api_evidence.py d1
    python capture_api_evidence.py d2
    python capture_api_evidence.py d3
    python capture_api_evidence.py d5

API 키는 .env에서만 읽고 화면에는 출력하지 않는다.
"""

import json
import sys
from pathlib import Path

import requests


BASE_URL = "http://localhost:5000/api/security/events"
STUDENT = "홍주형"


def get_api_key() -> str:
  env_path = Path(__file__).parent / "_7_board_test" / ".env"
  for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("SECURITY_API_KEY="):
      return line.split("=", 1)[1].strip()
  raise RuntimeError("_7_board_test/.env에서 SECURITY_API_KEY를 찾지 못했습니다.")


def print_response(response: requests.Response) -> None:
  print(f"HTTP_STATUS: {response.status_code}")
  try:
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
  except ValueError:
    print(response.text)


def main() -> int:
  if len(sys.argv) != 2 or sys.argv[1].lower() not in {"d1", "d2", "d3", "d5"}:
    print("사용법: python capture_api_evidence.py d1|d2|d3|d5")
    return 2

  case = sys.argv[1].lower()
  if case == "d1":
    print("=== D1: API 키 없이 POST → 401 기대 ===")
    response = requests.post(
        BASE_URL,
        json={"student": STUDENT, "src_ip": "1.2.3.114", "decision": "deny"},
        timeout=10,
    )
  elif case == "d2":
    print("=== D2: decision 누락 POST → 400 기대 ===")
    response = requests.post(
        BASE_URL,
        headers={"X-API-Key": get_api_key()},
        json={"student": STUDENT, "src_ip": "1.2.3.114"},
        timeout=10,
    )
  elif case == "d3":
    print("=== D3: 정상 POST → 201 + id 기대 ===")
    response = requests.post(
        BASE_URL,
        headers={"X-API-Key": get_api_key()},
        json={
            "student": STUDENT,
            "src_ip": "1.2.3.114",
            "decision": "deny",
            "severity": "High",
            "fail_count": 10,
            "reason": "level 10 rule 5712 deny",
        },
        timeout=10,
    )
  else:
    print("=== D5: 홍주형 이벤트 조회 → 200 기대 ===")
    response = requests.get(BASE_URL, params={"student": STUDENT}, timeout=10)

  print_response(response)
  expected = {"d1": 401, "d2": 400, "d3": 201, "d5": 200}[case]
  return 0 if response.status_code == expected else 1


if __name__ == "__main__":
  raise SystemExit(main())
