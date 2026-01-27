# Visitor Management System - Backend

A Django REST API backend for managing visitor registrations with async email processing using Celery.


superadmin and admin accounts.
Superadmin: superadmin@ifactory.com / superadmin123
Admin: admin@ifactory.com / admin123

## Features

- ✅ Visitor registration and management
- ✅ QR code generation for visitor verification
- ✅ Email notifications (visitor confirmations & host notifications)
- ✅ Bulk visitor upload with Excel files (up to 20 visitors)
- ✅ Async email processing with Celery for fast bulk uploads
- ✅ Slot-based booking system (20 visitors per hour)
- ✅ JWT authentication
- ✅ Analytics and reporting
- ✅ Automated visitor status updates

## Tech Stack

- **Framework**: Django 4.2.7
- **API**: Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production)
- **Task Queue**: Celery with Redis
- **Authentication**: JWT (Simple JWT)
- **Email**: SMTP (Gmail)
- **File Processing**: OpenPyXL for Excel files
- **QR Codes**: qrcode library

## Prerequisites

- Python 3.11+
- Redis (for Celery)
- PostgreSQL (for production)

## Local Development Setup

### 1. Clone the repository

```bash
cd vms_backend
```

### 2. Create virtual environment

```bash
python -m venv vms_env
```

### 3. Activate virtual environment

**Windows:**
```bash
vms_env\Scripts\activate
```

**Linux/Mac:**
```bash
source vms_env/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file in the backend directory:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (for production)
DATABASE_URL=postgresql://user:password@localhost:5432/vms_db

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=django-db

# Frontend URL
FRONTEND_URL=http://localhost:5173
```

### 6. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create superuser

```bash
python manage.py createsuperuser
```

### 8. Start Redis (required for Celery)

**Windows (using WSL or Docker):**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Linux/Mac:**
```bash
redis-server
```

### 9. Start Celery worker (in a new terminal)

```bash
# Activate virtual environment first
celery -A vms_backend worker --loglevel=info --pool=solo
```

**Note**: On Windows, use `--pool=solo` flag

### 10. Start Celery Beat (optional, for scheduled tasks)

```bash
celery -A vms_backend beat --loglevel=info
```

### 11. Run development server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

## Docker Deployment

### Using Docker Compose (Recommended)

1. **Build and start all services:**

```bash
docker-compose up -d --build
```

This will start:
- PostgreSQL database
- Redis
- Django backend (Gunicorn)
- Celery worker
- Celery beat

2. **Run migrations:**

```bash
docker-compose exec web python manage.py migrate
```

3. **Create superuser:**

```bash
docker-compose exec web python manage.py createsuperuser
```

4. **View logs:**

```bash
docker-compose logs -f
```

5. **Stop services:**

```bash
docker-compose down
```

### Using Docker only

```bash
# Build image
docker build -t vms-backend .

# Run container
docker run -d -p 8000:8000 --env-file .env vms-backend
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - Register new user
- `POST /api/auth/login/` - Login
- `POST /api/auth/token/refresh/` - Refresh token

### Visitors
- `GET /api/visitors/` - List all visitors
- `POST /api/visitors/` - Create visitor
- `GET /api/visitors/{id}/` - Get visitor details
- `PUT /api/visitors/{id}/` - Update visitor
- `DELETE /api/visitors/{id}/` - Delete visitor
- `POST /api/visitors/verify-qr/` - Verify QR code
- `POST /api/visitors/bulk-upload/` - Bulk upload visitors

### Bulk Upload
- `GET /api/visitors/download-template/` - Download Excel template
- `POST /api/visitors/bulk-upload/` - Upload Excel file with visitors

### Slots
- `GET /api/visitors/available-slots/?visit_date=YYYY-MM-DD` - Get available slots
- `GET /api/visitors/check-slot/?visit_date=YYYY-MM-DD&visit_time=HH:MM` - Check slot availability

### Analytics
- `GET /api/visitors/dashboard-stats/` - Get dashboard statistics
- `GET /api/visitors/export-excel/` - Export visitors to Excel

## Bulk Upload Performance Optimization

The bulk upload feature has been optimized for handling multiple concurrent users:

### Key Optimizations:

1. **Async Email Processing**: Emails are sent asynchronously using Celery, reducing upload time from ~60s to ~2s for 20 visitors

2. **Bulk Database Operations**: Using `bulk_create()` instead of individual `create()` calls

3. **Parallel Email Sending**: Celery workers process emails in parallel

4. **Immediate Response**: API returns immediately after creating visitors, emails are queued

### Performance Metrics:

- **Before**: ~3-5 seconds per visitor (60-100s for 20 visitors)
- **After**: ~0.1 seconds per visitor (~2s for 20 visitors)
- **Improvement**: ~30x faster

### Handling Concurrent Users:

The system can handle multiple users uploading simultaneously:
- Celery workers process tasks in parallel (4 workers by default)
- Redis queue manages task distribution
- Database transactions ensure data consistency

## Troubleshooting

### Celery not working

1. **Check Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

2. **Check Celery worker logs:**
```bash
celery -A vms_backend worker --loglevel=debug
```

3. **Verify Celery configuration:**
```bash
python manage.py shell
>>> from vms_backend import celery_app
>>> celery_app.control.inspect().active()
```

### Emails not sending

1. **Check email configuration in `.env`**
2. **Verify Gmail app password** (not regular password)
3. **Check Celery worker logs** for email task errors
4. **Test email manually:**
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Message', 'from@example.com', ['to@example.com'])
```

### Database migration errors

```bash
# Reset migrations (development only)
python manage.py migrate --fake visitors zero
python manage.py migrate visitors
```

## Production Deployment

### Environment Variables

Set these in your production environment:

```env
DEBUG=False
SECRET_KEY=<strong-random-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@host:5432/dbname
CELERY_BROKER_URL=redis://redis-host:6379/0
```

### Security Checklist

- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS
- [ ] Set up proper CORS configuration
- [ ] Use environment variables for sensitive data
- [ ] Configure proper email settings
- [ ] Set up Redis with authentication
- [ ] Configure firewall rules
- [ ] Set up monitoring and logging

### Recommended Production Stack

- **Web Server**: Gunicorn + Nginx
- **Database**: PostgreSQL 15+
- **Cache/Queue**: Redis 7+
- **Process Manager**: Supervisor or systemd
- **Container**: Docker + Docker Compose
- **Monitoring**: Sentry, Prometheus, Grafana

## Maintenance

### Daily Tasks (Automated)

- Cleanup expired visitors (runs at midnight via Celery Beat)

### Manual Tasks

- Backup database regularly
- Monitor Celery queue length
- Check email delivery logs
- Review error logs

## License

Proprietary - All rights reserved

## Support

For issues and questions, contact the development team.
