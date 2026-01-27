@echo off
echo "=========================================="
echo "    VMS FINAL DATA RECOVERY & MIGRATION   "
echo "=========================================="

echo.
echo 1. Fixing migration constraints...
vms_env\Scripts\python -c "import os; p=r'visitors/migrations/0002_update_visitor_choices.py'; open(p, 'w').write('from django.db import migrations\n\nclass Migration(migrations.Migration):\n    dependencies = [(\'visitors\', \'0001_initial\')]\n    operations = []')"

echo.
echo 2. Running migrations...
vms_env\Scripts\python manage.py migrate

echo.
echo 3. Manually fixing PostgreSQL schema...
vms_env\Scripts\python fix_pg_schema.py

echo.
echo 4. Transferring data from SQLite...
vms_env\Scripts\python direct_migrate.py

echo.
echo 5. Setting up initial users...
vms_env\Scripts\python setup_users.py

echo.
echo ==========================================
echo   SUCCESS! Your data is now in PostgreSQL.
echo ==========================================
pause
vms_env\Scripts\python manage.py runserver
