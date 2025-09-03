@echo off
echo ========================================
echo   SearchSmartly POI Importer
echo   One-Click Project Launcher
echo ========================================
echo.

REM Navigate to project directory
cd /d "%~dp0"

REM Check if we're in the right directory
if not exist "manage.py" (
    echo ERROR: manage.py not found!
    echo Please ensure this batch file is in the poi_ingest directory.
    pause
    exit /b 1
)

echo [1/5] Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.10+ first.
    pause
    exit /b 1
)

echo.
echo [2/5] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo [3/5] Setting up database...
python manage.py migrate
if errorlevel 1 (
    echo ERROR: Database migration failed!
    pause
    exit /b 1
)

echo.
echo [4/5] Creating demo admin user...
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poi_ingest.settings'); django.setup(); from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='demo', defaults={'email': 'demo@example.com', 'is_staff': True, 'is_superuser': True}); user.set_password('demo123'); user.save(); print('Demo user ready!')"

echo.
echo [5/5] Starting Django server...
echo.
echo ========================================
echo   PROJECT READY!
echo ========================================
echo   Admin: http://127.0.0.1:8000/admin/
echo   Login: demo / demo123
echo   API:   http://127.0.0.1:8000/api/poi/
echo ========================================
echo.
echo Starting server... (Press Ctrl+C to stop)
echo.

REM Start the server
python manage.py runserver

echo.
echo Server stopped.
pause
