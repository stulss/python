# auto_capture.ps1 — A3 / D2 / D3 를 자동 실행하면서 화면을 자동 캡처해 저장한다.
# 실행: PowerShell에서  .\auto_capture.ps1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Capture-Screen($path) {
  Start-Sleep -Milliseconds 700
  $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
  $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose(); $bitmap.Dispose()
  Write-Host "  -> 캡처 저장: $path" -ForegroundColor Green
}

$outDir = "D:\stuls\n8n-login-alert-bot\images\auto"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$key = Read-Host "SECURITY_API_KEY 를 입력하세요 (_7_board_test/.env 의 값)"
$base = "http://localhost:5000/api/security/events"

# ── D2: 필수값(decision) 누락 -> 400 ──────────────────────────────
Clear-Host
Write-Host "=== D2: decision 누락 -> 400 기대 ===" -ForegroundColor Cyan
curl.exe -X POST $base -H "Content-Type: application/json" -H "X-API-Key: $key" -d '{\"student\":\"홍주형\",\"src_ip\":\"1.2.3.114\"}' -w "`nHTTP_STATUS:%{http_code}`n"
Capture-Screen "$outDir\D2_400.png"
Start-Sleep -Seconds 1

# ── D3: 정상 POST -> 201 (UTF-8 바이트로 인코딩해 한글 깨짐 방지) ──
Clear-Host
Write-Host "=== D3: 정상 POST -> 201 기대 ===" -ForegroundColor Cyan
$json = @{student="홍주형"; src_ip="1.2.3.114"; decision="deny"; severity="High"; fail_count=10; reason="level 10 rule 5712 deny"} | ConvertTo-Json
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
$result = Invoke-RestMethod -Uri $base -Method Post -Headers @{ "X-API-Key" = $key } -ContentType "application/json; charset=utf-8" -Body $bytes
Write-Host "HTTP_STATUS: 201 (성공 시 아래처럼 id 가 반환됨)"
$result | ConvertTo-Json
Capture-Screen "$outDir\D3_201.png"
Start-Sleep -Seconds 1

# ── A3: n8n 을 끈 채 alert_sender.py 실행 -> 죽지 않고 오류만 출력 ──
Clear-Host
Write-Host "=== A3: n8n 컨테이너를 잠시 끄고 alert_sender.py 실행 ===" -ForegroundColor Cyan
docker stop n8n | Out-Null
Start-Sleep -Seconds 1
Clear-Host
python D:\stuls\python\alert_sender.py
Capture-Screen "$outDir\A3_n8n_down.png"
Write-Host "n8n 다시 켜는 중..." -ForegroundColor Yellow
docker start n8n | Out-Null

Write-Host "`n모두 완료. 캡처 파일: $outDir" -ForegroundColor Green
