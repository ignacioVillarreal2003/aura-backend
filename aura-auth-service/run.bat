@echo off
REM Development commands for Aura Auth Service (Windows)
REM Usage: run.bat [command]

setlocal enabledelayedexpansion

if "%1"=="" goto show_help

set "COMMAND=%1"

if /i "%COMMAND%"=="help" goto show_help
if /i "%COMMAND%"=="install" goto install_deps
if /i "%COMMAND%"=="migrate" goto run_migrate
if /i "%COMMAND%"=="makemigrations" goto make_migrations
if /i "%COMMAND%"=="setup" goto setup_db
if /i "%COMMAND%"=="shell" goto django_shell
if /i "%COMMAND%"=="runserver" goto run_server
if /i "%COMMAND%"=="createsuperuser" goto create_superuser
if /i "%COMMAND%"=="check" goto check_setup
if /i "%COMMAND%"=="clean" goto clean_cache

echo Unknown command: %COMMAND%
goto show_help

:show_help
echo.
echo Aura Authentication Service - Development Commands
echo ===================================================
echo.
echo Usage: run.bat [command]
echo.
echo Commands:
echo   help              - Show this help message
echo   install           - Install dependencies from requirements.txt
echo   makemigrations    - Create database migrations
echo   migrate           - Apply database migrations
echo   setup             - Run full database setup (migrations + seed + superuser)
echo   shell             - Open Django shell
echo   runserver         - Start development server (http://localhost:8000)
echo   createsuperuser   - Create a new superuser
echo   check             - Check project configuration
echo   clean             - Clean Python cache files
echo.
goto :eof

:install_deps
echo Installing dependencies...
pip install -r requirements.txt
goto :eof

:make_migrations
echo Creating migrations...
python manage.py makemigrations accounts
goto :eof

:run_migrate
echo Applying migrations...
python manage.py migrate
goto :eof

:setup_db
echo Running full database setup...
python scripts/setup_db.py
goto :eof

:django_shell
echo Opening Django shell...
python manage.py shell
goto :eof

:run_server
echo Starting development server...
echo Open http://localhost:8000/admin/ in your browser
python manage.py runserver
goto :eof

:create_superuser
echo Creating superuser...
python manage.py createsuperuser
goto :eof

:check_setup
echo Checking project setup...
python manage.py check
goto :eof

:clean_cache
echo Cleaning Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
for /r . %%f in (*.pyc) do @if exist "%%f" del /q "%%f"
echo Cache cleaned!
goto :eof
