#!/usr/bin/env python
"""
Fix database sequence issue for VisitorLog
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vms_backend.settings")
django.setup()

from visitors.models import VisitorLog
from django.db import connection, models

# Get the maximum ID from VisitorLog
max_id = VisitorLog.objects.all().aggregate(models.Max("id"))["id__max"]
print(f"Max VisitorLog ID: {max_id}")

# Reset the sequence
with connection.cursor() as cursor:
    if max_id:
        cursor.execute(f"SELECT setval('visitors_visitorlog_id_seq', {max_id + 1});")
        print(f"Set sequence to: {max_id + 1}")
    else:
        cursor.execute("SELECT setval('visitors_visitorlog_id_seq', 1);")
        print("Set sequence to: 1")

print("✅ VisitorLog sequence fixed!")

# Also check and fix Visitor sequence
from visitors.models import Visitor

max_visitor_id = Visitor.objects.all().aggregate(models.Max("id"))["id__max"]
print(f"\nMax Visitor ID: {max_visitor_id}")

with connection.cursor() as cursor:
    if max_visitor_id:
        # For UUID, we don't need to fix the sequence, but let's check
        print("Visitor uses UUID, no sequence needed")
    else:
        print("No visitors in database")

print("\n✅ All sequences checked and fixed!")
