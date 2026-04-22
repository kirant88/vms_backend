# Host Management Views - to be added to visitors/views.py

# Add these imports at the top:
# from .models import Host
# from .serializers import HostSerializer

# Add these CRUD endpoint views at the end of visitors/views.py:

# Host Management CRUD Endpoints


class HostListCreateView(generics.ListCreateAPIView):
    """List all hosts or create a new host"""

    queryset = Host.objects.filter(is_active=True)
    serializer_class = HostSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated admins

    def get_queryset(self):
        """Filter hosts by active status"""
        return Host.objects.filter(is_active=True).order_by("name")

    def perform_create(self, serializer):
        """Create a new host"""
        serializer.save()


class HostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific host"""

    queryset = Host.objects.all()
    serializer_class = HostSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated admins
    lookup_field = "id"

    def perform_destroy(self, instance):
        """Soft delete - mark as inactive instead of hard delete"""
        instance.is_active = False
        instance.save()


@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_hosts(request):
    """Get all active hosts for dropdown (public endpoint for frontend)"""
    try:
        hosts = (
            Host.objects.filter(is_active=True)
            .values("id", "name", "email", "contact_no")
            .order_by("name")
        )
        return Response({"hosts": list(hosts), "total": hosts.count()})
    except Exception as e:
        return Response(
            {"error": f"Failed to fetch hosts: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
