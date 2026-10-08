# ==============================================================================
# AgentOps End-to-End Verification & Smoke Test Script (PowerShell)
# ==============================================================================

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   AgentOps End-to-End Clean Verification Suite   " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$root = Resolve-Path "$PSScriptRoot\.."
$pytestPath = "$root\.venv\Scripts\pytest.exe"
$pythonPath = "$root\.venv\Scripts\python.exe"

# 1. Run Backend Pytest Suite
Write-Host "`n[1/4] Running Backend Automated Tests (Pytest)..." -ForegroundColor Yellow
$backendTest = Start-Process -FilePath $pytestPath -ArgumentList "-v" -WorkingDirectory "$root\backend" -NoNewWindow -Wait -PassThru
if ($backendTest.ExitCode -ne 0) {
    Write-Host "Backend tests failed with exit code $($backendTest.ExitCode)!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ All 64 Backend Tests Passed!" -ForegroundColor Green

# 2. Run Frontend Unit Tests
Write-Host "`n[2/4] Running Frontend Vitest Suite..." -ForegroundColor Yellow
$frontendTest = Start-Process -FilePath "npx.cmd" -ArgumentList "vitest run" -WorkingDirectory "$root\frontend" -NoNewWindow -Wait -PassThru
if ($frontendTest.ExitCode -ne 0) {
    Write-Host "Frontend tests failed with exit code $($frontendTest.ExitCode)!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ All Frontend Tests Passed!" -ForegroundColor Green

# 3. Next.js Production Build Test
Write-Host "`n[3/4] Verifying Next.js Production Build..." -ForegroundColor Yellow
$buildTest = Start-Process -FilePath "npm.cmd" -ArgumentList "run build" -WorkingDirectory "$root\frontend" -NoNewWindow -Wait -PassThru
if ($buildTest.ExitCode -ne 0) {
    Write-Host "Next.js build failed with exit code $($buildTest.ExitCode)!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Next.js Build Succeeded!" -ForegroundColor Green

# 4. Verify Seeding Process
Write-Host "`n[4/4] Verifying Deterministic Database Seeding..." -ForegroundColor Yellow
$seedTest = Start-Process -FilePath $pythonPath -ArgumentList "app/scripts/seed_data.py" -WorkingDirectory "$root\backend" -NoNewWindow -Wait -PassThru
if ($seedTest.ExitCode -ne 0) {
    Write-Host "Database seed process failed!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Database Seeding Succeeded!" -ForegroundColor Green

Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "   ALL VERIFICATIONS PASSED (Clean Environment)   " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
