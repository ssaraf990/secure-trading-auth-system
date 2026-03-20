# Start Flask Server
Write-Host "Starting IS Lab Project Server..." -ForegroundColor Green
Write-Host "Initializing database..." -ForegroundColor Yellow

cd $PSScriptRoot
python -c "from app import init_db; init_db(); print('Database ready!')"

Write-Host "Starting Flask server on http://127.0.0.1:5001" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python app.py

