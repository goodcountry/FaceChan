"""
federation/api_views.py

DRF API endpoints for the federation management dashboard.
All views are admin-only — hardcoded check, same pattern as purge.
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from core.models import Board, SiteSettings
from core.permissions import can_purge_content
from federation.models import (
    RemoteInstance, RemoteBoard, RemoteBoardMapping, Follow, FederationActivity
)


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

class IsAdminTier(permissions.BasePermission):
    """Allows access only to users with an admin-tier role.

    Delegates to core.permissions.can_purge_content, which is the single
    source of truth for the admin-tier check (requires role.is_admin_tier
    AND role.can_purge). Purge capability is the hardcoded admin marker.
    """
    def has_permission(self, request, view):
        return can_purge_content(request.user)


class AdminDashboardMixin:
    """Shared config for federation dashboard endpoints.

    The dashboard frontend consumes these list endpoints as plain arrays
    (it filters/maps them client-side over a small number of rows), so
    pagination is disabled — a paginated {results: [...]} object would
    break the frontend's array handling. All endpoints are admin-tier only.
    """
    permission_classes = [IsAdminTier]
    pagination_class = None


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class RemoteInstanceSerializer(serializers.ModelSerializer):
    board_count = serializers.SerializerMethodField()
    mapping_count = serializers.SerializerMethodField()
    pending_follows = serializers.SerializerMethodField()

    class Meta:
        model = RemoteInstance
        fields = [
            'id', 'domain', 'status', 'actor_url', 'notes',
            'created_at', 'updated_at', 'board_count', 'mapping_count',
            'pending_follows',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_board_count(self, obj):
        return obj.remote_boards.count()

    def get_mapping_count(self, obj):
        return obj.board_mappings.count()

    def get_pending_follows(self, obj):
        return Follow.objects.filter(
            remote_actor__instance=obj, accepted=False
        ).count()


class RemoteBoardSerializer(serializers.ModelSerializer):
    is_mapped = serializers.SerializerMethodField()
    mapped_to = serializers.SerializerMethodField()
    follow_accepted = serializers.SerializerMethodField()

    class Meta:
        model = RemoteBoard
        fields = [
            'id', 'remote_slug', 'name', 'description', 'nsfw',
            'actor_url', 'fetched_at', 'is_mapped', 'mapped_to', 'follow_accepted',
        ]

    def get_is_mapped(self, obj):
        return RemoteBoardMapping.objects.filter(
            instance=obj.instance, remote_slug=obj.remote_slug
        ).exists()

    def get_mapped_to(self, obj):
        try:
            mapping = RemoteBoardMapping.objects.select_related('local_board').get(
                instance=obj.instance, remote_slug=obj.remote_slug
            )
            return {'slug': mapping.local_board.slug, 'name': mapping.local_board.name}
        except RemoteBoardMapping.DoesNotExist:
            return None

    def get_follow_accepted(self, obj):
        try:
            mapping = RemoteBoardMapping.objects.get(
                instance=obj.instance, remote_slug=obj.remote_slug
            )
            return mapping.follow_accepted  # None, False, or True
        except RemoteBoardMapping.DoesNotExist:
            return None


class LocalBoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ['slug', 'name', 'description', 'nsfw', 'allow_federation']


class RemoteBoardMappingSerializer(serializers.ModelSerializer):
    remote_board_name = serializers.SerializerMethodField()
    local_board_name = serializers.SerializerMethodField()
    instance_domain = serializers.SerializerMethodField()
    # The dashboard works in slugs throughout (the dropdown is keyed on slug
    # and LocalBoardSerializer exposes slug, not id), so accept the local
    # board by slug rather than PK.
    local_board = serializers.SlugRelatedField(
        slug_field='slug', queryset=Board.objects.all()
    )

    class Meta:
        model = RemoteBoardMapping
        fields = [
            'id', 'instance', 'remote_slug', 'local_board',
            'remote_board_name', 'local_board_name', 'instance_domain',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_remote_board_name(self, obj):
        try:
            rb = RemoteBoard.objects.get(instance=obj.instance, remote_slug=obj.remote_slug)
            return rb.name
        except RemoteBoard.DoesNotExist:
            return obj.remote_slug

    def get_local_board_name(self, obj):
        return obj.local_board.name

    def get_instance_domain(self, obj):
        return obj.instance.domain


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class FederationStatusView(APIView):
    """GET /api/federation/status/ — instance-level federation status."""
    permission_classes = [IsAdminTier]

    def get(self, request):
        from federation.utils import is_federation_configured, base_url
        settings = SiteSettings.get()
        return Response({
            'federation_enabled': settings.federation_enabled,
            'federation_configured': is_federation_configured(),
            'base_url': base_url(),
            'instance_count': RemoteInstance.objects.filter(status='approved').count(),
            'pending_count': RemoteInstance.objects.filter(status='pending').count(),
            'blocked_count': RemoteInstance.objects.filter(status='blocked').count(),
            'total_mappings': RemoteBoardMapping.objects.count(),
        })

    def patch(self, request):
        """Toggle federation_enabled."""
        settings = SiteSettings.get()
        enabled = request.data.get('federation_enabled')
        if enabled is not None:
            settings.federation_enabled = bool(enabled)
            settings.save(update_fields=['federation_enabled'])
        return Response({'federation_enabled': settings.federation_enabled})


class RemoteInstanceListView(AdminDashboardMixin, generics.ListCreateAPIView):
    """
    GET  /api/federation/instances/ — list all remote instances
    POST /api/federation/instances/ — add a new instance (triggers board fetch if approved)
    """
    serializer_class = RemoteInstanceSerializer

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        qs = RemoteInstance.objects.all()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by('domain')


class RemoteInstanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/federation/instances/<pk>/
    PATCH  /api/federation/instances/<pk>/ — update status/notes
    DELETE /api/federation/instances/<pk>/
    """
    permission_classes = [IsAdminTier]
    serializer_class = RemoteInstanceSerializer
    queryset = RemoteInstance.objects.all()


class RefreshInstanceBoardsView(APIView):
    """
    POST /api/federation/instances/<pk>/refresh/
    Re-fetch the remote instance's board list from /ap/instance.
    """
    permission_classes = [IsAdminTier]

    def post(self, request, pk):
        try:
            instance = RemoteInstance.objects.get(pk=pk)
        except RemoteInstance.DoesNotExist:
            return Response({'error': 'not found'}, status=404)

        if not instance.is_approved:
            return Response({'error': 'instance must be approved first'}, status=400)

        from federation.tasks import fetch_instance_boards
        fetch_instance_boards.delay(str(instance.pk))
        return Response({'status': 'refresh queued'})


class RemoteBoardListView(AdminDashboardMixin, generics.ListAPIView):
    """GET /api/federation/instances/<pk>/boards/ — cached remote boards."""
    serializer_class = RemoteBoardSerializer

    def get_queryset(self):
        return RemoteBoard.objects.filter(
            instance_id=self.kwargs['pk']
        ).order_by('remote_slug')


def _trigger_follow_for_mapping(mapping):
    """
    Send an outbound Follow for a freshly created/updated board mapping, so
    the remote instance begins delivering that board's threads to us.

    Skips quietly (mapping still works for inbound filing) when federation
    is paused/unconfigured or the remote board isn't cached yet.
    """
    from federation.models import Actor, RemoteBoard
    from federation.utils import is_federation_configured
    from core.models import SiteSettings

    if not is_federation_configured() or not SiteSettings.get().federation_enabled:
        return

    local_actor, _ = Actor.objects.get_or_create(
        board=mapping.local_board, defaults={'actor_type': 'Group'}
    )

    remote_board = RemoteBoard.objects.filter(
        instance=mapping.instance, remote_slug=mapping.remote_slug
    ).first()
    if remote_board is None:
        return

    from federation.tasks import deliver_follow
    deliver_follow.delay(str(local_actor.pk), str(remote_board.pk))

    # Mark follow as pending — will be set to True when Accept arrives
    mapping.follow_accepted = False
    mapping.save(update_fields=['follow_accepted'])


class RemoteBoardMappingListView(AdminDashboardMixin, generics.ListCreateAPIView):
    """
    GET  /api/federation/mappings/ — all board mappings
    POST /api/federation/mappings/ — create a mapping
    """
    serializer_class = RemoteBoardMappingSerializer

    def get_queryset(self):
        instance_id = self.request.query_params.get('instance')
        qs = RemoteBoardMapping.objects.select_related(
            'instance', 'local_board'
        )
        if instance_id:
            qs = qs.filter(instance_id=instance_id)
        return qs.order_by('instance__domain', 'remote_slug')

    def perform_create(self, serializer):
        """
        After saving the mapping, follow the remote board so its instance
        starts delivering that board's threads to us. Mapping a remote board
        to a local one expresses "send me this board's content" — a Follow is
        the ActivityPub mechanism for exactly that.
        """
        mapping = serializer.save()
        _trigger_follow_for_mapping(mapping)


class RemoteBoardMappingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/federation/mappings/<pk>/
    PATCH  /api/federation/mappings/<pk>/
    DELETE /api/federation/mappings/<pk>/
    """
    permission_classes = [IsAdminTier]
    serializer_class = RemoteBoardMappingSerializer
    queryset = RemoteBoardMapping.objects.all()

    def perform_update(self, serializer):
        """
        Re-mapping (changing the local board, or re-saving an existing
        mapping) also (re)sends the Follow so the remote instance delivers
        to us. Idempotent remote-side: _handle_follow get_or_creates and
        re-accepts.
        """
        mapping = serializer.save()
        _trigger_follow_for_mapping(mapping)


class LocalBoardListView(AdminDashboardMixin, generics.ListAPIView):
    """
    GET /api/federation/local-boards/
    Lists local boards for the mapping dropdown.
    """
    serializer_class = LocalBoardSerializer

    def get_queryset(self):
        return Board.objects.all().order_by('slug')
