@echo off
REM Windows batch file for common Django management tasks

if "%1"=="help" goto help
if "%1"=="setup" goto setup
if "%1"=="install" goto install
if "%1"=="migrate" goto migrate
if "%1"=="run" goto run
if "%1"=="superuser" goto superuser
if "%1"=="load-sample" goto load-sample
if "%1"=="test" goto test
if "%1"=="clean" goto clean

:help
echo Available commands:
echo   manage.bat setup        - Complete development setup
echo   manage.bat install      - Install dependencies
echo   manage.bat migrate      - Run database migrations
echo   manage.bat run          - Start development server
echo   manage.bat superuser    - Create superuser
echo   manage.bat load-sample  - Load sample POI data
echo   manage.bat test         - Run test suite
echo   manage.bat clean        - Clean cache files
goto end

:setup
echo Setting up development environment...
echo Ensuring required directories exist...
if not exist "poi_ingest\logs" mkdir poi_ingest\logs
call :install
call :migrate
echo.
echo Development setup complete!
echo Next steps:
echo   manage.bat load-sample  # Load sample data
echo   manage.bat superuser    # Create admin user
echo   manage.bat run          # Start development server
goto end

:install
echo Installing dependencies...
pip install -r requirements.txt
goto end

:migrate
echo Running database migrations...
echo Ensuring required directories exist...
if not exist "poi_ingest\logs" mkdir poi_ingest\logs
python manage.py makemigrations
python manage.py migrate
goto end

:run
echo Starting development server...
python manage.py runserver
goto end

:superuser
echo Creating superuser...
python manage.py createsuperuser
goto end

:load-sample
echo Loading sample POI data from ../data/
if exist "../data" (
    python manage.py import_poi ../data/ --verbose
    echo.
    echo Sample data loaded successfully!
    echo.
    echo Access the application at:
    echo   Admin: http://localhost:8000/admin/
    echo   API:   http://localhost:8000/api/poi/
    echo   Health: http://localhost:8000/health/
) else (
    echo Error: ../data/ directory not found
    echo Please ensure the data directory exists with sample files:
    echo   ../data/pois.csv
    echo   ../data/JsonData.json  
    echo   ../data/XmlData.xml
)
goto end

:test
echo Running test suite...
python manage.py test
goto end

:clean
echo Cleaning cache and temporary files...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
if exist ".coverage" del ".coverage"
if exist "htmlcov" rd /s /q "htmlcov"
if exist ".pytest_cache" rd /s /q ".pytest_cache"
echo Cache cleaned!
goto end

:end
