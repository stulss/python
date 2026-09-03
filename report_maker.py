# report_with_date.py
import json
from datetime import datetime

alerts = [
    {"level": 12, "ip": "1.1.1.1", "severity": "High"},
    {"level": 9,  "ip": "2.2.2.2", "severity": "Medium"},
    {"level": 3,  "ip": "3.3.3.3", "severity": "Low"},
]

filename = f'report_{datetime.now().strftime("%Y%m%d_%H%M")}.md'

with open(filename, "w", encoding="utf-8") as f:
    f.write(f'# 경보 리포트\n')
    f.write(f'생성: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n')
    f.write("| IP | 레벨 | 심각도 |\n|---|---|---|\n")
    for a in alerts:
        f.write(f'| {a["ip"]} | {a["level"]} | {a["severity"]} |\n')

print(f"리포트 생성 완료: {filename}")