from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Count, Q
from datetime import datetime, timedelta
from visitors.models import Visitor, Department


@api_view(["GET"])
@permission_classes([AllowAny])
def analytics_dashboard(request):
    """Analytics dashboard data"""
    today = datetime.now().date()

    stats = {
        "total_visitors": Visitor.objects.count(),
        "today_visitors": Visitor.objects.filter(visit_date=today).count(),
        "verified_visitors": Visitor.objects.filter(status="verified").count(),
        "pending_visitors": Visitor.objects.filter(status="pending").count(),
    }

    department_stats = (
        Visitor.objects.values("department__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

  
    purpose_stats = (
        Visitor.objects.values("purpose").annotate(count=Count("id")).order_by("-count")
    )

    return Response(
        {
            "stats": stats,
            "department_stats": list(department_stats),
            "purpose_stats": list(purpose_stats),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def visitor_trends(request):
    """Visitor trends over time"""
    days = int(request.GET.get("days", 7))
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    trends = []
    current_date = start_date

    while current_date <= end_date:
        count = Visitor.objects.filter(visit_date=current_date).count()
        trends.append({"date": current_date.isoformat(), "visitors": count})
        current_date += timedelta(days=1)

    return Response({"trends": trends})


@api_view(["GET"])
@permission_classes([AllowAny])
def department_stats(request):
    """Department statistics"""
    stats = []
    departments = Department.objects.all()

    for dept in departments:
        visitor_count = Visitor.objects.filter(department=dept).count()
        stats.append(
            {
                "department": dept.name,
                "visitors": visitor_count,
                "percentage": (
                    round((visitor_count / Visitor.objects.count() * 100), 2)
                    if Visitor.objects.count() > 0
                    else 0
                ),
            }
        )

    return Response({"department_stats": stats})


@api_view(["GET"])
@permission_classes([AllowAny])
def hourly_stats(request):
    """Hourly visitor statistics"""
    from django.db.models import Count
    from django.db.models.functions import Extract

   
    today = datetime.now().date()
    hourly_data = (
        Visitor.objects.filter(visit_date=today)
        .annotate(hour=Extract("visit_time", "hour"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )

    # Create a 9 AM to 6 PM array (hours 9-18)
    hourly_stats = []
    for hour in range(9, 19): 
        count = 0
        for data in hourly_data:
            if data["hour"] == hour:
                count = data["count"]
                break
        hourly_stats.append({"hour": hour, "count": count})

    return Response({"hourly_stats": hourly_stats})
