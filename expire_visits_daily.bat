@echo off
REM Batch script to expire old visits
REM This script should be run daily via Windows Task Scheduler

cd /d "d:\Vision Lab project\Visitor Management System - Full Stack\vms_backend"

REM Activate virtual environment
call vms_env\Scripts\activate.bat

REM Run the expire visits command
python manage.py expire_visits

REM Log the execution
echo %date% %time% - Expire visits command executed >> expire_visits_log.txt

REM Deactivate virtual environment
deactivate
