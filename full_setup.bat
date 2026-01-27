@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   VMS PostgreSQL ^& User Auto-Setup
echo ===================================================
echo.

set /p db_pass="Enter your PostgreSQL password [default: postgres]: "
if "!db_pass!"=="" set db_pass=postgres

echo.
echo 1. Creating .env file...
(
echo DB_NAME=ifactory_vms_db
echo DB_USER=postgres
echo DB_PASSWORD=!db_pass!
echo DB_HOST=localhost
echo DB_PORT=5432
echo SECRET_KEY=django-insecure-vms-default-key
echo DEBUG=True
echo FRONTEND_URL=http://localhost:5173
echo ALLOWED_HOSTS=localhost,127.0.0.1
) > .env
echo [DONE] .env file created with your password.

echo.
echo 2. Creating Database (if not exists)...
set PGPASSWORD=!db_pass!
psql -U postgres -h localhost -c "CREATE DATABASE ifactory_vms_db;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [DONE] Database created.
) else (
    echo [INFO] Database might already exist.
)

echo.
echo 3. Running Migrations...
vms_env\Scripts\python manage.py makemigrations authentication visitors analytics
vms_env\Scripts\python manage.py migrate

echo.
echo 4. Setting up Superadmin and Admin users...
vms_env\Scripts\python setup_users.py

echo.
echo ===================================================
echo   SETUP COMPLETE!
echo ===================================================
echo.
echo You can now login with:
echo   Username/Email: admin@ifactory.com
echo   Password: admin123
echo.
echo Or Superadmin:
echo   Username/Email: superadmin@ifactory.com
echo   Password: superadmin123
echo.
echo Starting server now...
echo.
vms_env\Scripts\python manage.py runserver
pause
