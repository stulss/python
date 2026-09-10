# auto_capture_cafe.ps1 — 카페이야기 접근 제어 실습 과제 실제 화면 자동 캡처 스크립트
# 실행 방법: PowerShell에서 .\auto_capture_cafe.ps1 실행

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$outDir = "D:\stuls\python\_8_cafe_story\screenshots"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Capture-Screen($filename) {
    Start-Sleep -Milliseconds 1200
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $path = Join-Path $outDir $filename
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
    Write-Host "  -> [캡처 성공] $path" -ForegroundColor Green
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " ☕ 카페이야기 접근 제어(RBAC) 제출용 실제 화면 자동 캡처 시작 " -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

# ── 1. 실제 MySQL DB 콘솔 조회 화면 ────────────────────────────────
Clear-Host
Write-Host "=== [1-1] MySQL 데이터베이스 cafe_users 테이블 권한(role_level) 확인 ===" -ForegroundColor Cyan
python D:\stuls\python\_8_cafe_story\view_db.py
Capture-Screen "real_01_db_console.png"

# Chrome 경로 확인
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
    $chrome = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
}

# ── 2. 일반회원 로그인 헤더 및 메인 화면 ──────────────────────────────
Write-Host "`n=== [1-2] 일반회원(user1) 로그인 헤더(유저명, 일반회원 Lv.0 표기) ===" -ForegroundColor Cyan
Start-Process $chrome "http://127.0.0.1:5000/switch-account?user=user1&next=/" -WindowStyle Maximized
Start-Sleep -Seconds 3
Capture-Screen "real_02_user_header.png"

# ── 3. 일반회원의 골드 라운지 접속 시도 -> 403 예외 ─────────────────
Write-Host "`n=== [2-1] 일반회원의 골드 라운지 접속 시도 -> 403 Forbidden 예외 화면 ===" -ForegroundColor Cyan
Start-Process $chrome "http://127.0.0.1:5000/switch-account?user=user1&next=/gold"
Start-Sleep -Seconds 3
Capture-Screen "real_03_user_gold_denied.png"

# ── 4. 일반회원의 관리자 센터 접속 시도 -> 403 예외 ─────────────────
Write-Host "`n=== [2-2] 일반회원의 관리자 센터 접속 시도 -> 403 Forbidden 예외 화면 ===" -ForegroundColor Cyan
Start-Process $chrome "http://127.0.0.1:5000/switch-account?user=user1&next=/admin"
Start-Sleep -Seconds 3
Capture-Screen "real_04_user_admin_denied.png"

# ── 5. 골드회원의 골드 라운지 접속 성공 화면 ────────────────────────
Write-Host "`n=== [2-3] 골드회원(golduser)의 골드 라운지 접속 성공 (헤더: 골드회원 Lv.1) ===" -ForegroundColor Cyan
Start-Process $chrome "http://127.0.0.1:5000/switch-account?user=golduser&next=/gold"
Start-Sleep -Seconds 3
Capture-Screen "real_05_gold_success.png"

# ── 6. 골드회원의 관리자 센터 접속 시도 -> 403 예외 ─────────────────
Write-Host "`n=== [2-4] 골드회원의 관리자 센터 접속 시도 -> 403 Forbidden 예외 화면 ===" -ForegroundColor Cyan
Start-Process $chrome "http://127.0.0.1:5000/switch-account?user=golduser&next=/admin"
Start-Sleep -Seconds 3
Capture-Screen "real_06_gold_admin_denied.png"

# ── 7. 관리자의 관리자 센터 접속 성공 및 회원정보 수정/삭제 화면 ───────
Write-Host "`n=== [2-5] 관리자(admin)의 관리자 센터 접속 성공 및 회원 수정/삭제 화면 ===" -ForegroundColor Cyan
Start-Process $chrome "http://127.0.0.1:5000/switch-account?user=admin&next=/admin"
Start-Sleep -Seconds 3
Capture-Screen "real_07_admin_success.png"

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host " 🎉 모든 실제 화면 캡처 완료! 저장 폴더: $outDir" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Green