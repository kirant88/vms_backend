from rest_framework import serializers
from .models import Visitor, Department, VisitorLog


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class VisitorSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Visitor
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "company",
            "visitor_type",
            "visitor_category",
            "purpose",
            "department",
            "department_name",
            "visit_date",
            "visit_time",
            "host_name",
            "host_email",
            "status",
            "qr_code",
            "qr_image",
            "created_at",
            "updated_at",
            "checked_in_at",
            "checked_out_at",
            "notes",
            "is_active",
        ]
        read_only_fields = ["qr_code", "qr_image", "created_at", "updated_at"]

    def get_department_name(self, obj):
        """Return department name or None if department is not set"""
        return obj.department.name if obj.department else None


class VisitorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = [
            "name",
            "email",
            "phone",
            "company",
            "visitor_type",
            "visitor_category",
            "purpose",
            "department",
            "visit_date",
            "visit_time",
            "host_name",
            "host_email",
            "notes",
        ]


class VisitorLogSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source="visitor.name", read_only=True)

    class Meta:
        model = VisitorLog
        fields = ["id", "visitor", "visitor_name", "action", "timestamp", "notes"]


class QRVerificationSerializer(serializers.Serializer):
    qr_code = serializers.CharField(max_length=200, trim_whitespace=True)
