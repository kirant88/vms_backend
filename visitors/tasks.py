from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_visitor_email_async(self, visitor_id):
    """
    Async task to send visitor confirmation email
    """
    try:
        from visitors.models import Visitor
        from utils.email_service_memory import send_visitor_confirmation_memory_only
        
        visitor = Visitor.objects.get(id=visitor_id)
        send_visitor_confirmation_memory_only(visitor)
        logger.info(f"Successfully sent email to visitor {visitor.email}")
        return f"Email sent to {visitor.email}"
    except Visitor.DoesNotExist:
        logger.error(f"Visitor with ID {visitor_id} not found")
        return f"Visitor {visitor_id} not found"
    except Exception as e:
        logger.error(f"Failed to send email to visitor {visitor_id}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_host_notification_async(self, visitor_id):
    """
    Async task to send host notification email
    """
    try:
        from visitors.models import Visitor
        from utils.email_service_memory import send_host_notification
        
        visitor = Visitor.objects.get(id=visitor_id)
        send_host_notification(visitor)
        logger.info(f"Successfully sent host notification for visitor {visitor.email}")
        return f"Host notification sent for {visitor.email}"
    except Visitor.DoesNotExist:
        logger.error(f"Visitor with ID {visitor_id} not found")
        return f"Visitor {visitor_id} not found"
    except Exception as e:
        logger.error(f"Failed to send host notification for visitor {visitor_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def send_bulk_host_notification_async(host_name, host_email, visitors, visit_date, visit_time, purpose):
    """
    Async task to send bulk host notification email
    """
    try:
        from utils.email_service_memory import send_bulk_host_notification
        
        send_bulk_host_notification(
            host_name=host_name,
            host_email=host_email,
            visitors=visitors,
            visit_date=visit_date,
            visit_time=visit_time,
            purpose=purpose
        )
        logger.info(f"Successfully sent bulk notification to host {host_email}")
        return f"Bulk notification sent to {host_email}"
    except Exception as e:
        logger.error(f"Failed to send bulk notification to host {host_email}: {str(e)}")
        return f"Failed: {str(e)}"


@shared_task
def process_bulk_visitor_emails(visitor_ids):
    """
    Process multiple visitor emails in parallel
    """
    from celery import group
    
    # Create a group of tasks to run in parallel
    job = group(send_visitor_email_async.s(visitor_id) for visitor_id in visitor_ids)
    result = job.apply_async()
    
    return f"Processing {len(visitor_ids)} visitor emails"


@shared_task
def cleanup_expired_visitors():
    """
    Scheduled task to cleanup expired visitors
    """
    try:
        from visitors.views import update_expired_visitors
        result = update_expired_visitors()
        logger.info(f"Cleaned up expired visitors: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to cleanup expired visitors: {str(e)}")
        return f"Failed: {str(e)}"
