from rest_framework import viewsets, generics, status, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db.models import Count, F, Case, When, IntegerField, Q
from django.db import models as db_models
from .models import User, Board, Community, Membership, Thread, Post, Reaction, SiteSettings, Report, DisplayNameChangeLog, WatchedThread, FeedItem, ActivityTier, CommunityInvite, SitePage
from .serializers import (
    UserSerializer, RegisterSerializer, BoardSerializer,
    CommunitySerializer, CommunityDetailSerializer, MembershipSerializer,
    ThreadListSerializer, ThreadDetailSerializer,
    PostSerializer, ReplySerializer, SiteSettingsSerializer, ReportSerializer,
    ModReportSerializer, SanctionedUserSerializer,
    CommunityInviteSerializer, CommunityInvitePreviewSerializer,
    SitePageSerializer, SitePageListSerializer,
    ConversationListSerializer, ConversationDetailSerializer,
)
from .image_utils import process_image, process_avatar, compute_perceptual_hash, generate_thumbnail
from .video_utils import process_video, extract_video_thumbnail, compute_video_perceptual_hash
from .csam_detection import scan_image, report_match
from .permissions import (
    can_moderate, hide_content, unhide_content,
    quarantine_content, restore_from_quarantine, purge_content, can_purge_content,
    pin_thread, unpin_thread, set_comments_disabled, can_access_private_thread
)
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def _create_report(request, *, thread=None, post=None):
    """
    Shared report-creation logic for threads and posts.
    Returns a DRF Response — caller just returns it.
    """
    if not SiteSettings.get().enable_content_reporting:
        return Response({'error': 'Content reporting is disabled on this instance.'}, status=403)

    reason = request.data.get('reason')
    valid_reasons = dict(Report.REASON_CHOICES)
    if reason not in valid_reasons:
        return Response({'error': f'reason must be one of: {", ".join(valid_reasons)}'}, status=400)

    # Prevent duplicate open reports from the same user on the same target
    existing = Report.objects.filter(reporter=request.user, status__in=['open', 'reviewing'])
    existing = existing.filter(thread=thread) if thread else existing.filter(post=post)
    if existing.exists():
        return Response({'error': 'You have already reported this — it is awaiting review.'}, status=400)

    # Snapshot fields, captured now while the content definitely still
    # exists — see Report model docstring. This is what lets the mod
    # queue still show who/what/where was reported even after the
    # content itself is purged, which the live thread/post relation
    # alone can't survive (it goes to NULL on purge, by design).
    target = thread or post
    board = thread.board if thread else post.thread.board
    preview_source = thread.title if thread else post.body

    report = Report.objects.create(
        reporter=request.user,
        thread=thread,
        post=post,
        target_type='thread' if thread else 'post',
        target_author=target.author,
        target_author_username=target.author.username if target.author else '',
        target_board_slug=board.slug,
        target_preview_snapshot=preview_source[:200],
        target_poster_ip=target.poster_ip,
        reason=reason,
        details=request.data.get('details', '')[:1000],
    )
    return Response(ReportSerializer(report).data, status=201)


def _check_daily_limit(user, queryset, limit, label):
    """
    Raise Throttled if the user has hit their limit within a rolling 24-hour
    window (not a calendar-day reset — the window slides with the clock).
    0 = unlimited.
    """
    if not limit:
        return
    since = timezone.now() - timedelta(hours=24)
    count = queryset.filter(author=user, created_at__gte=since).count()
    if count >= limit:
        from rest_framework.exceptions import Throttled
        raise Throttled(
            detail=f"Limit reached: {limit} {label} per rolling 24 hours. "
                   f"This isn't a midnight reset — it'll free up as your oldest "
                   f"{label[:-1] if label.endswith('s') else label} in that window ages past 24h."
        )


def _age_gate_passed(request):
    """
    True if the client has confirmed the age gate for NSFW content.

    Logged-in users: checked against User.age_verified, persisted server-side,
    so confirmation carries across devices/browsers once logged in.

    Logged-out/anonymous users: no account exists to persist against, so this
    falls back to the client-side flow — the frontend sends X-Age-Verified
    once the user has confirmed via the AgeGate component, stored client-side
    in localStorage. Per design, logged-out users never see NSFW boards
    regardless of any prior confirmation in an earlier session.
    """
    user = request.user
    if user and user.is_authenticated:
        return bool(user.age_verified)
    return request.headers.get('X-Age-Verified') == 'true'


def _nsfw_gate_active():
    settings = SiteSettings.get()
    return settings.enable_nsfw_boards and settings.block_nsfw_without_age_gate


def _get_poster_ip(request):
    """
    Extract the real client IP. In prod, Nginx is in front and sets
    X-Forwarded-For; we take the leftmost address (the original client).
    Falls back to REMOTE_ADDR for direct connections.

    Dev note: on Docker Desktop (Windows/Mac), REMOTE_ADDR and
    X-Forwarded-For will be a Docker bridge gateway IP (172.x.x.x)
    because Docker Desktop NATs host traffic before it reaches the
    container network. This is unavoidable in that environment.
    Real client IPs will be logged correctly in prod on a Linux host.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


import re as _re
_URL_RE = _re.compile(r'https?://', _re.IGNORECASE)


def _check_links_allowed(site_settings, board, fields: dict):
    """
    Raise ValidationError if a hyperlink (http:// or https://) is found in
    any of the supplied text fields and links are not permitted.

    ``fields`` maps field name → text value, e.g. {'title': '...', 'body': '...'}.
    The check is skipped entirely when links are allowed (fast path).
    """
    # Global master switch takes precedence
    if not site_settings.allow_links:
        for field_name, text in fields.items():
            if text and _URL_RE.search(text):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    field_name: 'Hyperlinks are not permitted on this instance.'
                })
        return

    # Global is on — check per-board setting
    if not board.allow_links:
        for field_name, text in fields.items():
            if text and _URL_RE.search(text):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    field_name: 'Hyperlinks are not permitted on this board.'
                })


def _exclude_hidden_and_quarantined(qs, user):
    """
    Shared visibility filter for Thread/Post querysets. Quarantine excludes
    EVERYONE including the author (stronger than hide, by design — see
    core/permissions.py). Hide excludes everyone except the author.
    """
    qs = qs.filter(is_quarantined=False)
    if user.is_authenticated:
        return qs.filter(Q(is_hidden=False) | Q(author=user))
    return qs.filter(is_hidden=False)


class SiteSettingsView(generics.RetrieveAPIView):
    """Public endpoint — returns site settings so the frontend can read site name etc."""
    permission_classes = [permissions.AllowAny]
    serializer_class = SiteSettingsSerializer

    def get_object(self):
        return SiteSettings.get()


class SitePageDetailView(generics.RetrieveAPIView):
    """Public endpoint — returns a single published site page by slug."""
    permission_classes = [permissions.AllowAny]
    serializer_class = SitePageSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return SitePage.objects.filter(published=True)


class SitePageListView(generics.ListAPIView):
    """Public endpoint — returns footer pages (published + show_in_footer)."""
    permission_classes = [permissions.AllowAny]
    serializer_class = SitePageListSerializer
    pagination_class = None

    def get_queryset(self):
        return SitePage.objects.filter(published=True, show_in_footer=True)


class SitePageEditView(generics.RetrieveUpdateAPIView):
    """Staff endpoint — edit a site page. Requires can_manage_pages on the user's role."""
    lookup_field = 'slug'

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        return SitePageSerializer

    def get_queryset(self):
        return SitePage.objects.all()

    def check_permissions(self, request):
        super().check_permissions(request)
        from .permissions import can_manage_pages
        if not can_manage_pages(request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have permission to manage site pages.')

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        if not SiteSettings.get().registration_open:
            return Response({'error': 'Registration is currently closed on this instance.'}, status=403)
        from .captcha import run_bot_checks
        bot_check = run_bot_checks(request.data)
        if bot_check:
            return bot_check
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': UserSerializer(user).data}, status=201)


class LoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
        if not user:
            return Response({'error': 'Invalid credentials'}, status=400)
        if user.is_banned:
            return Response({'error': 'This account has been permanently banned.'}, status=403)
        if user.is_suspended:
            return Response({
                'error': f'This account is suspended until {user.suspended_until.isoformat()}.',
                'suspended_until': user.suspended_until.isoformat(),
            }, status=403)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': UserSerializer(user).data})


def get_or_create_dm_board():
    """
    The hidden system board that holds every private-message thread.
    is_system=True keeps it out of BoardViewSet's public listing and out of
    the normal board-assignment UI for board-scoped staff (see Board.is_system
    help_text and can_access_private_thread in permissions.py). Federation is
    off both here and via the is_private_message guard in federation/signals.py.
    """
    board, _ = Board.objects.get_or_create(
        slug='_dm',
        defaults={
            'name': 'Private Messages',
            'description': 'System board — holds private message threads. Not a real board.',
            'icon': '✉️',
            'allow_images': True,
            'allow_videos': True,
            'allow_video_sound': True,
            'allow_links': True,
            'allow_federation': False,
            'is_system': True,
        }
    )
    return board


class BoardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BoardSerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Board.objects.annotate(thread_count=Count('threads')).order_by('name').exclude(is_system=True)
        user = self.request.user
        if not (user and user.is_authenticated and _age_gate_passed(self.request)):
            qs = qs.exclude(nsfw=True)
        return qs


class CommunityViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CommunityDetailSerializer
        return CommunitySerializer

    def get_queryset(self):
        from django.db.models import Count, Q, OuterRef, Subquery
        from django.utils import timezone
        from datetime import timedelta
        from .models import Post

        now = timezone.now()
        window_48h = now - timedelta(hours=48)
        window_24h = now - timedelta(hours=24)

        # Recent post activity annotations — counted via thread relation
        # to avoid a direct Community→Post join (Post has no FK to Community).
        qs = Community.objects.annotate(
            member_count=Count('members', distinct=True),
            active_posts=Count(
                'threads__posts',
                filter=Q(threads__posts__created_at__gte=window_48h),
                distinct=True,
            ),
            trending_posts=Count(
                'threads__posts',
                filter=Q(threads__posts__created_at__gte=window_24h),
                distinct=True,
            ),
        )

        # Board filter
        board = self.request.query_params.get('board')
        if board:
            qs = qs.filter(board__slug=board)

        # Name search
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Hide private communities the user isn't a member of
        user = self.request.user
        if user.is_authenticated:
            qs = qs.filter(
                Q(is_private=False) |
                Q(is_private=True, members=user)
            )
        else:
            qs = qs.filter(is_private=False)

        # Sort modes
        sort = self.request.query_params.get('sort', 'members')
        if sort == 'newest':
            qs = qs.order_by('-created_at')
        elif sort == 'active':
            qs = qs.order_by('-active_posts', '-member_count')
        elif sort == 'trending':
            qs = qs.order_by('-trending_posts', '-member_count')
        else:  # members (default)
            qs = qs.order_by('-member_count', 'name')

        return qs.distinct()

    def perform_create(self, serializer):
        if not SiteSettings.get().enable_communities:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Communities are disabled on this instance.')
        user = self.request.user
        # Enforce community creation limits
        FREE_LIMIT = 1
        PRO_LIMIT = 10
        limit = PRO_LIMIT if user.is_premium else FREE_LIMIT
        owned = Community.objects.filter(created_by=user).count()
        if owned >= limit:
            from rest_framework.exceptions import PermissionDenied
            if user.is_premium:
                raise PermissionDenied(
                    f'PRO accounts can create up to {PRO_LIMIT} communities. You have {owned}.'
                )
            else:
                raise PermissionDenied(
                    f'Free accounts can create {FREE_LIMIT} community. '
                    f'Upgrade to PRO to create up to {PRO_LIMIT}.'
                )
        community = serializer.save(created_by=user)
        # Creator automatically becomes admin member
        from .models import Membership
        Membership.objects.get_or_create(
            user=user,
            community=community,
            defaults={'role': 'admin'}
        )

    @action(detail=True, methods=['post'])
    def join(self, request, slug=None):
        community = self.get_object()
        if community.is_private:
            return Response({'error': 'This community is private.'}, status=403)
        # Use get_or_create to avoid duplicate Membership rows
        _, created = Membership.objects.get_or_create(
            user=request.user, community=community, defaults={'role': 'member'}
        )
        return Response({'joined': True, 'already_member': not created,
                         'member_count': community.members.count()})

    @action(detail=True, methods=['post'])
    def leave(self, request, slug=None):
        community = self.get_object()
        membership = Membership.objects.filter(user=request.user, community=community).first()
        if not membership:
            return Response({'error': 'You are not a member.'}, status=400)

        if membership.role == 'admin':
            admin_count = Membership.objects.filter(community=community, role='admin').count()
            if admin_count <= 1:
                # Last admin — require explicit confirmation via /leave-and-delete/
                return Response({
                    'error': 'You are the last admin. Leaving will permanently delete this community.',
                    'must_confirm_delete': True
                }, status=400)
            else:
                # Other admins exist — they must demote themselves first
                return Response({
                    'error': 'Admins cannot leave while still an admin. Use the role dropdown to demote yourself to member first.',
                    'must_demote_first': True
                }, status=400)

        membership.delete()
        return Response({'left': True, 'member_count': community.members.count()})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='leave-and-delete')
    def leave_and_delete(self, request, slug=None):
        """Last admin explicitly confirms they want to leave and delete the community."""
        community = self.get_object()
        membership = Membership.objects.filter(user=request.user, community=community).first()
        if not membership or membership.role != 'admin':
            return Response({'error': 'Only admins can use this endpoint.'}, status=403)
        admin_count = Membership.objects.filter(community=community, role='admin').count()
        if admin_count > 1:
            return Response({'error': 'There are other admins. Use the regular leave endpoint.'}, status=400)
        community_name = community.name
        community.delete()
        return Response({'left': True, 'community_deleted': True,
                         'message': f'"{community_name}" has been deleted.'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='set-role')
    def set_role(self, request, slug=None):
        """Admin can change a member's role (member ↔ mod ↔ admin)."""
        community = self.get_object()
        requester = Membership.objects.filter(user=request.user, community=community).first()
        if not requester or requester.role != 'admin':
            return Response({'error': 'Only admins can change roles.'}, status=403)
        username = request.data.get('username', '').strip()
        new_role = request.data.get('role', '').strip()
        if new_role not in ('member', 'mod', 'admin'):
            return Response({'error': 'Role must be member, mod, or admin.'}, status=400)
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': f'User "{username}" not found.'}, status=404)
        if target_user == request.user:
            return Response({'error': 'Use leave-and-delete to remove your own admin role.'}, status=400)
        target_membership = Membership.objects.filter(user=target_user, community=community).first()
        if not target_membership:
            return Response({'error': f'{username} is not a member.'}, status=400)
        target_membership.role = new_role
        target_membership.save()
        from .serializers import MemberRosterSerializer as _MS
        return Response(_MS(target_membership).data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def members(self, request, slug=None):
        """List all members of a community, ordered by role then join date."""
        community = self.get_object()
        if community.is_private and not community.members.filter(pk=request.user.pk).exists():
            return Response({'error': 'Members only.'}, status=403)
        memberships = Membership.objects.filter(community=community).select_related('user').order_by(
            Case(
                When(role='admin', then=0),
                When(role='mod', then=1),
                default=2,
                output_field=IntegerField()
            ), 'joined_at'
        )
        from .serializers import MemberRosterSerializer as _MS
        return Response(_MS(memberships, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='add-member')
    def add_member(self, request, slug=None):
        """Admin/mod can add a user by username."""
        community = self.get_object()
        requester_membership = Membership.objects.filter(user=request.user, community=community).first()
        if not requester_membership or requester_membership.role not in ('admin', 'mod'):
            return Response({'error': 'Only admins and mods can add members.'}, status=403)
        username = request.data.get('username', '').strip()
        if not username:
            return Response({'error': 'Username is required.'}, status=400)
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': f'User "{username}" not found.'}, status=404)
        membership, created = Membership.objects.get_or_create(
            user=target, community=community, defaults={'role': 'member'}
        )
        if not created:
            return Response({'error': f'{username} is already a member.'}, status=400)
        from .serializers import MemberRosterSerializer as _MS
        return Response(_MS(membership).data, status=201)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='remove-member')
    def remove_member(self, request, slug=None):
        """Admin/mod can remove a member by username."""
        community = self.get_object()
        requester_membership = Membership.objects.filter(user=request.user, community=community).first()
        if not requester_membership or requester_membership.role not in ('admin', 'mod'):
            return Response({'error': 'Only admins and mods can remove members.'}, status=403)
        username = request.data.get('username', '').strip()
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': f'User "{username}" not found.'}, status=404)
        if target == request.user:
            return Response({'error': 'Use the leave endpoint to remove yourself.'}, status=400)
        deleted, _ = Membership.objects.filter(user=target, community=community).delete()
        if deleted == 0:
            return Response({'error': f'{username} is not a member.'}, status=400)
        return Response({'removed': True, 'username': username})

    @action(detail=True, methods=['get', 'post'], permission_classes=[permissions.IsAuthenticated], url_path='invites')
    def invites(self, request, slug=None):
        """
        GET  — list active invites for this community (admin/mod only).
        POST — create a new invite link (admin/mod only).
                Body: { expires_in_days: int|null, max_uses: int|null }
        """
        community = self.get_object()
        membership = Membership.objects.filter(user=request.user, community=community).first()
        if not membership or membership.role not in ('admin', 'mod'):
            return Response({'error': 'Only admins and mods can manage invites.'}, status=403)

        if request.method == 'GET':
            invites = CommunityInvite.objects.filter(community=community, is_active=True).order_by('-created_at')
            return Response(CommunityInviteSerializer(invites, many=True, context={'request': request}).data)

        # POST — create
        from datetime import timedelta
        expires_in_days = request.data.get('expires_in_days')
        max_uses = request.data.get('max_uses')
        expires_at = None
        if expires_in_days:
            try:
                expires_at = timezone.now() + timedelta(days=int(expires_in_days))
            except (ValueError, TypeError):
                return Response({'error': 'expires_in_days must be an integer.'}, status=400)
        if max_uses is not None:
            try:
                max_uses = int(max_uses)
                if max_uses < 1:
                    raise ValueError
            except (ValueError, TypeError):
                return Response({'error': 'max_uses must be a positive integer.'}, status=400)

        invite = CommunityInvite.objects.create(
            community=community,
            created_by=request.user,
            expires_at=expires_at,
            max_uses=max_uses,
        )
        return Response(CommunityInviteSerializer(invite, context={'request': request}).data, status=201)

    @action(detail=True, methods=['delete'], permission_classes=[permissions.IsAuthenticated],
            url_path=r'invites/(?P<token>[0-9a-f-]+)')
    def revoke_invite(self, request, slug=None, token=None):
        """Admin/mod can revoke (deactivate) an invite by token."""
        community = self.get_object()
        membership = Membership.objects.filter(user=request.user, community=community).first()
        if not membership or membership.role not in ('admin', 'mod'):
            return Response({'error': 'Only admins and mods can revoke invites.'}, status=403)
        try:
            invite = CommunityInvite.objects.get(token=token, community=community)
        except CommunityInvite.DoesNotExist:
            return Response({'error': 'Invite not found.'}, status=404)
        invite.is_active = False
        invite.save(update_fields=['is_active'])
        return Response({'revoked': True})

    @action(detail=True, methods=['get'])
    def threads(self, request, slug=None):
        """Threads for this community — private ones gated to members only."""
        community = self.get_object()
        user = request.user

        if community.is_private:
            if not user.is_authenticated or not community.members.filter(pk=user.pk).exists():
                return Response({'error': 'Members only.'}, status=403)

        if community.board and community.board.nsfw and _nsfw_gate_active() and not _age_gate_passed(request):
            return Response({'error': 'This community is age-gated.', 'nsfw_gate': True}, status=403)

        qs = Thread.objects.filter(community=community).select_related('author', 'board').order_by('-is_pinned', '-last_reply_at')
        qs = _exclude_hidden_and_quarantined(qs, user)
        serializer = ThreadListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class InvitePreviewView(generics.RetrieveAPIView):
    """
    Public endpoint — returns community info for the invite landing page.
    Anyone can view this; the invite may be invalid/expired but is still
    shown so the user understands what they were invited to.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = CommunityInvitePreviewSerializer
    lookup_field = 'token'
    queryset = CommunityInvite.objects.select_related('community', 'community__board')


class InviteJoinView(generics.GenericAPIView):
    """
    POST /api/invites/:token/join/
    Authenticated users join the community via a valid invite.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, token):
        try:
            invite = CommunityInvite.objects.select_related('community').get(token=token)
        except CommunityInvite.DoesNotExist:
            return Response({'error': 'Invite not found.'}, status=404)

        if not invite.is_valid():
            return Response({'error': 'This invite link has expired or been revoked.'}, status=400)

        community = invite.community
        _, created = Membership.objects.get_or_create(
            user=request.user, community=community, defaults={'role': 'member'}
        )
        if created:
            CommunityInvite.objects.filter(pk=invite.pk).update(use_count=db_models.F('use_count') + 1)

        return Response({
            'joined': True,
            'already_member': not created,
            'community_slug': community.slug,
            'community_name': community.name,
        })


class ThreadViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        # Private-message threads are never reachable through the ordinary
        # Thread endpoints — they only exist via ConversationViewSet. This
        # exclusion is defense-in-depth: they live on a hidden board that
        # nothing else here queries for anyway, but a thread ID could still
        # be guessed/leaked, so keep this explicit rather than relying on
        # obscurity.
        qs = Thread.objects.select_related('author', 'board', 'community').exclude(is_private_message=True)

        board = self.request.query_params.get('board')
        community = self.request.query_params.get('community')
        user = self.request.user

        if community:
            # Community-scoped — handled by CommunityViewSet.threads
            qs = qs.filter(community__slug=community)
        elif board:
            # Board view — show public threads only (no private community threads)
            qs = qs.filter(board__slug=board).filter(
                Q(community__isnull=True) |
                Q(community__is_private=False)
            )
            # Board-scoped search — title and body
            search = self.request.query_params.get('search', '').strip()
            if search:
                qs = qs.filter(Q(title__icontains=search) | Q(body__icontains=search))
        else:
            # General — exclude private community threads
            qs = qs.filter(
                Q(community__isnull=True) |
                Q(community__is_private=False)
            )

        # NSFW age-gating: exclude NSFW-board threads unless the client has
        # confirmed the gate. A specific ?board= request for an NSFW board
        # still gets fully excluded here too — BoardDetail shows the gate
        # prompt instead of calling this endpoint until confirmed.
        if _nsfw_gate_active() and not _age_gate_passed(self.request):
            qs = qs.exclude(board__nsfw=True)

        # Hidden/quarantined content: hidden excluded for everyone except
        # its own author; quarantined excluded for EVERYONE including the
        # author. Staff review both via the mod queue, not by it silently
        # appearing in the general feed for anyone holding a staff role.
        qs = _exclude_hidden_and_quarantined(qs, user)

        return qs.order_by('-is_pinned', '-last_reply_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ThreadDetailSerializer
        return ThreadListSerializer

    def create(self, request, *args, **kwargs):
        from .captcha import run_bot_checks
        bot_check = run_bot_checks(request.data)
        if bot_check:
            return bot_check
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        settings = SiteSettings.get()
        _check_daily_limit(
            self.request.user, Thread.objects,
            settings.max_threads_per_user_per_day, 'threads'
        )
        board_slug = self.request.data.get('board')
        community_slug = self.request.data.get('community')
        board = Board.objects.get(slug=board_slug)
        if board.is_system:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('This board does not accept ordinary threads.')
        if board.nsfw and _nsfw_gate_active() and not _age_gate_passed(self.request):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('This board is age-gated. Confirm your age to post here.')
        community = None
        if community_slug:
            community = Community.objects.get(slug=community_slug)
            # Check membership for private communities
            if community.is_private and not community.members.filter(pk=self.request.user.pk).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You are not a member of this community.')
        # Check hyperlinks in title and body before any media processing
        _check_links_allowed(settings, board, {
            'title': self.request.data.get('title', ''),
            'body': self.request.data.get('body', ''),
        })
        # Process image upload if present — validate BEFORE saving the thread
        # so a rejected image doesn't leave an orphaned thread behind
        image_file = self.request.FILES.get('image')
        user_may_post_media = settings.allow_image_uploads or self.request.user.can_post_media
        if image_file and not board.allow_images:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'image': 'This board does not allow image uploads.'})
        if image_file and not user_may_post_media:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'image': 'Image uploads are disabled on this instance.'})
        processed = None
        if image_file:
            max_bytes = settings.max_image_size_mb * 1024 * 1024
            try:
                processed = process_image(image_file, max_upload_bytes=max_bytes)
            except ValueError as e:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'image': str(e)})

            # Permanent floor — not configurable, no SiteSettings toggle.
            # See core/csam_detection.py: this currently always returns
            # NOT_IMPLEMENTED, it does not actually scan anything yet.
            scan_result = scan_image(processed.getvalue())
            if scan_result.is_flagged:
                report_match(scan_result, context={
                    'uploader_id': str(self.request.user.pk),
                    'target': 'thread',
                })
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'image': 'This image could not be accepted.'})
            processed.seek(0)

        # Process video upload if present — mutually exclusive with image
        user_may_post_video = settings.allow_video_uploads or self.request.user.can_post_media
        video_file = self.request.FILES.get('video')
        if video_file and image_file:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'video': 'Cannot attach both an image and a video.'})
        if video_file and not board.allow_videos:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'video': 'This board does not allow video uploads.'})
        if video_file and not user_may_post_video:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'video': 'Video uploads are disabled on this instance.'})
        processed_video = None
        if video_file:
            max_bytes = settings.max_video_size_mb * 1024 * 1024
            try:
                processed_video = process_video(
                    video_file,
                    max_upload_bytes=max_bytes,
                    max_duration_seconds=settings.max_video_duration_seconds,
                    allow_sound=board.allow_video_sound,
                )
            except ValueError as e:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'video': str(e)})

            # CSAM checkpoint on first frame — same permanent floor as images
            pdq = compute_video_perceptual_hash(
                processed_video['video_bytes'], processed_video['extension']
            )
            scan_result = scan_image(processed_video['video_bytes'])
            if scan_result.is_flagged:
                report_match(scan_result, context={
                    'uploader_id': str(self.request.user.pk),
                    'target': 'thread_video',
                })
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'video': 'This video could not be accepted.'})

        thread = serializer.save(
            author=self.request.user,
            board=board,
            community=community,
            poster_ip=_get_poster_ip(self.request),
        )
        if processed:
            image_bytes = processed.read()
            pdq = compute_perceptual_hash(image_bytes)
            thumb = generate_thumbnail(image_bytes)
            filename = f"{thread.id}.webp"
            thread.image.save(filename, ContentFile(image_bytes), save=False)
            thread.image_pdq_hash = pdq
            if thumb:
                thread.thumbnail.save(f"{thread.id}_thumb.webp", ContentFile(thumb.read()), save=False)
            thread.save(update_fields=['image', 'image_pdq_hash', 'thumbnail'])

        if processed_video:
            vbytes = processed_video['video_bytes']
            ext    = processed_video['extension']
            filename = f"{thread.id}{ext}"
            thread.video.save(filename, ContentFile(vbytes), save=False)
            thread.video_duration = processed_video['duration']
            thread.video_pdq_hash = compute_video_perceptual_hash(vbytes, ext)
            vthumb = extract_video_thumbnail(vbytes, ext)
            if vthumb:
                thread.video_thumbnail.save(f"{thread.id}_vthumb.webp", ContentFile(vthumb.read()), save=False)
            thread.save(update_fields=['video', 'video_duration', 'video_pdq_hash', 'video_thumbnail'])

        # Prune oldest non-pinned thread on this board if over the limit (0 = unlimited)
        if settings.max_threads_per_board:
            board_threads = Thread.objects.filter(board=board, is_pinned=False).order_by('-last_reply_at')
            excess = board_threads.count() - settings.max_threads_per_board
            if excess > 0:
                stale_ids = list(board_threads.values_list('pk', flat=True)[
                    settings.max_threads_per_board:settings.max_threads_per_board + excess
                ])
                Thread.objects.filter(pk__in=stale_ids).delete()

        # Increment author's post count
        User.objects.filter(pk=self.request.user.pk).update(post_count=F('post_count') + 1)

        # Auto-watch: the author starts watching their own thread, so they
        # get notified (bell + feed) on replies without an extra manual step.
        # last_seen_reply_count starts at the thread's current reply_count
        # (0 for a brand new thread) so nothing is retroactively marked
        # unread.
        WatchedThread.objects.get_or_create(
            user=self.request.user, thread=thread,
            defaults={'last_seen_reply_count': thread.reply_count},
        )

    def retrieve(self, request, *args, **kwargs):
        # Look up directly rather than via get_object()/get_queryset(), since
        # the queryset excludes ungated NSFW threads entirely — we want a
        # clear 403 + nsfw_gate flag here, not a misleading 404.
        try:
            instance = Thread.objects.select_related('board', 'community').get(pk=kwargs['pk'])
        except Thread.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('No Thread matches the given query.')
        if instance.is_private_message:
            # Never reachable here — use ConversationViewSet instead. Same
            # 404-not-403 treatment as hidden/quarantined content below, so
            # this endpoint doesn't confirm a private thread ID even exists.
            from rest_framework.exceptions import NotFound
            raise NotFound('No Thread matches the given query.')
        if instance.board.nsfw and _nsfw_gate_active() and not _age_gate_passed(request):
            return Response({'error': 'This board is age-gated.', 'nsfw_gate': True}, status=403)
        # Gate private community threads
        if instance.community and instance.community.is_private:
            user = request.user
            if not user.is_authenticated or not instance.community.members.filter(pk=user.pk).exists():
                return Response({'error': 'Members only.'}, status=403)
        if instance.is_quarantined:
            user = request.user
            is_admin = user.is_authenticated and user.role and user.role.is_admin_tier
            if not is_admin:
                from rest_framework.exceptions import NotFound
                raise NotFound('No Thread matches the given query.')
        if instance.is_hidden:
            user = request.user
            is_own = user.is_authenticated and instance.author_id == user.pk
            staff_can_see = user.is_authenticated and can_moderate(user, instance, 'can_hide')
            if not (is_own or staff_can_see):
                from rest_framework.exceptions import NotFound
                raise NotFound('No Thread matches the given query.')
        Thread.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def react(self, request, pk=None):
        thread = self.get_object()
        emoji = request.data.get('emoji')
        existing = Reaction.objects.filter(user=request.user, thread=thread)
        if existing.filter(emoji=emoji).exists():
            existing.delete()
            return Response({'action': 'removed'})
        existing.delete()
        Reaction.objects.create(user=request.user, thread=thread, emoji=emoji)
        return Response({'action': 'added'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def report(self, request, pk=None):
        # Look up directly, bypassing get_queryset()'s NSFW exclusion —
        # reporting must work regardless of age-gate status. Someone
        # reporting NSFW-board content (possibly because it's worse than
        # just adult content) shouldn't have to pass the age gate first.
        try:
            thread = Thread.objects.get(pk=pk)
        except Thread.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('No Thread matches the given query.')
        return _create_report(request, thread=thread)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def pin(self, request, pk=None):
        thread = self.get_object()
        if not can_moderate(request.user, thread, 'can_pin_threads'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have permission to pin threads here.')
        pin_thread(thread)
        return Response({'is_pinned': True, 'comments_disabled': True})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def unpin(self, request, pk=None):
        thread = self.get_object()
        if not can_moderate(request.user, thread, 'can_pin_threads'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have permission to unpin threads here.')
        unpin_thread(thread)
        return Response({'is_pinned': False, 'comments_disabled': False})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated],
            url_path='toggle-comments')
    def toggle_comments(self, request, pk=None):
        thread = self.get_object()
        if not can_moderate(request.user, thread, 'can_pin_threads'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have permission to toggle comments here.')
        disabled = request.data.get('disabled')
        if disabled is None:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'disabled': 'This field is required.'})
        set_comments_disabled(thread, disabled=bool(disabled))
        return Response({'comments_disabled': thread.comments_disabled})


class PostViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.data.get('parent_id'):
            return ReplySerializer
        return PostSerializer

    def get_queryset(self):
        thread_pk = self.kwargs.get('thread_pk')
        qs = Post.objects.filter(
            thread=thread_pk,
            parent__isnull=True
        ).select_related('author').prefetch_related(
            'reactions', 'replies__author', 'replies__reactions'
        ).order_by('created_at')

        # Private-message gate: this endpoint is also how conversation
        # messages are listed/posted/edited/reacted-to/reported (it's the
        # same Post model and the same URL shape, nested under thread_pk).
        # A non-participant gets an empty queryset here, which propagates
        # to 404s on retrieve/react/report/edit via get_object() — same
        # not-confirming-existence treatment as hidden/quarantined content.
        try:
            thread = Thread.objects.only('id', 'is_private_message').get(pk=thread_pk)
        except Thread.DoesNotExist:
            return qs.none()
        if not can_access_private_thread(self.request.user, thread):
            return qs.none()

        return _exclude_hidden_and_quarantined(qs, self.request.user)

    def create(self, request, *args, **kwargs):
        from .captcha import run_bot_checks
        bot_check = run_bot_checks(request.data)
        if bot_check:
            return bot_check
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        thread = Thread.objects.select_related('board').get(pk=self.kwargs['thread_pk'])

        if not can_access_private_thread(self.request.user, thread):
            from rest_framework.exceptions import NotFound
            raise NotFound('No Thread matches the given query.')

        if thread.is_locked:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('This thread is locked and no longer accepting replies.')

        if thread.board.nsfw and _nsfw_gate_active() and not _age_gate_passed(self.request):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('This board is age-gated. Confirm your age to reply here.')

        settings = SiteSettings.get()
        _check_daily_limit(
            self.request.user, Post.objects,
            settings.max_posts_per_user_per_day, 'posts'
        )

        parent_id = self.request.data.get('parent_id')

        # Check hyperlinks in body before any media processing
        _check_links_allowed(settings, thread.board, {
            'body': self.request.data.get('body', ''),
        })

        # Validate image BEFORE saving the post so a rejected image
        # doesn't leave an orphaned post behind
        image_file = self.request.FILES.get('image')
        user_may_post_media = settings.allow_image_uploads or self.request.user.can_post_media
        if image_file and not thread.board.allow_images:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'image': 'This board does not allow image uploads.'})
        if image_file and not user_may_post_media:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'image': 'Image uploads are disabled on this instance.'})
        processed = None
        if image_file:
            max_bytes = settings.max_image_size_mb * 1024 * 1024
            try:
                processed = process_image(image_file, max_upload_bytes=max_bytes)
            except ValueError as e:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'image': str(e)})

            # Permanent floor — not configurable, no SiteSettings toggle.
            # See core/csam_detection.py: this currently always returns
            # NOT_IMPLEMENTED, it does not actually scan anything yet.
            scan_result = scan_image(processed.getvalue())
            if scan_result.is_flagged:
                report_match(scan_result, context={
                    'uploader_id': str(self.request.user.pk),
                    'target': 'post',
                    'thread_id': str(thread.pk),
                })
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'image': 'This image could not be accepted.'})
            processed.seek(0)

        # Process video upload if present — mutually exclusive with image
        user_may_post_video = settings.allow_video_uploads or self.request.user.can_post_media
        video_file = self.request.FILES.get('video')
        if video_file and image_file:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'video': 'Cannot attach both an image and a video.'})
        if video_file and not thread.board.allow_videos:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'video': 'This board does not allow video uploads.'})
        if video_file and not user_may_post_video:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'video': 'Video uploads are disabled on this instance.'})
        processed_video = None
        if video_file:
            max_bytes = settings.max_video_size_mb * 1024 * 1024
            try:
                processed_video = process_video(
                    video_file,
                    max_upload_bytes=max_bytes,
                    max_duration_seconds=settings.max_video_duration_seconds,
                    allow_sound=thread.board.allow_video_sound,
                )
            except ValueError as e:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'video': str(e)})

            scan_result = scan_image(processed_video['video_bytes'])
            if scan_result.is_flagged:
                report_match(scan_result, context={
                    'uploader_id': str(self.request.user.pk),
                    'target': 'post_video',
                    'thread_id': str(thread.pk),
                })
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'video': 'This video could not be accepted.'})

        parent = None
        poster_ip = _get_poster_ip(self.request)
        if parent_id:
            parent = Post.objects.get(pk=parent_id, thread=thread)
            post = serializer.save(author=self.request.user, thread=thread, parent=parent, poster_ip=poster_ip)
        else:
            next_num = Post.objects.filter(thread=thread, parent__isnull=True).count() + 1
            post = serializer.save(author=self.request.user, thread=thread, post_number=next_num, poster_ip=poster_ip)
            Thread.objects.filter(pk=thread.pk).update(reply_count=F('reply_count') + 1)
            thread.refresh_from_db()

            # Bump thread to top unless sage, bump-locked, or post-limit reached
            is_sage = self.request.data.get('sage', False)
            bump_locked = False
            if settings.bump_lock_percent and settings.max_posts_per_thread:
                # Cap at 95% — values of 96-100+ would bump-lock threads that
                # are effectively full, and 100% makes the threshold equal to
                # the lock limit which causes undefined ordering behaviour.
                effective_percent = min(settings.bump_lock_percent, 95)
                bump_threshold = int(
                    settings.max_posts_per_thread * effective_percent / 100
                )
                bump_locked = thread.reply_count >= bump_threshold

            if not is_sage and not bump_locked:
                Thread.objects.filter(pk=thread.pk).update(last_reply_at=timezone.now())

            # Auto-lock once the thread hits its post limit (0 = unlimited)
            if settings.max_posts_per_thread:
                if thread.reply_count >= settings.max_posts_per_thread:
                    Thread.objects.filter(pk=thread.pk).update(is_locked=True)

        if processed:
            image_bytes = processed.read()
            pdq = compute_perceptual_hash(image_bytes)
            thumb = generate_thumbnail(image_bytes)
            filename = f"{post.id}.webp"
            post.image.save(filename, ContentFile(image_bytes), save=False)
            post.image_pdq_hash = pdq
            if thumb:
                post.thumbnail.save(f"{post.id}_thumb.webp", ContentFile(thumb.read()), save=False)
            post.save(update_fields=['image', 'image_pdq_hash', 'thumbnail'])

        if processed_video:
            vbytes = processed_video['video_bytes']
            ext    = processed_video['extension']
            filename = f"{post.id}{ext}"
            post.video.save(filename, ContentFile(vbytes), save=False)
            post.video_duration = processed_video['duration']
            post.video_pdq_hash = compute_video_perceptual_hash(vbytes, ext)
            vthumb = extract_video_thumbnail(vbytes, ext)
            if vthumb:
                post.video_thumbnail.save(f"{post.id}_vthumb.webp", ContentFile(vthumb.read()), save=False)
            post.save(update_fields=['video', 'video_duration', 'video_pdq_hash', 'video_thumbnail'])
        # Increment author's post count for all posts and replies
        User.objects.filter(pk=self.request.user.pk).update(post_count=F('post_count') + 1)

        # Auto-watch: replying to a thread starts watching it too, so the
        # replier gets notified of further activity without a manual step.
        # last_seen_reply_count is set to the thread's reply_count as of
        # this reply (already incremented above) — not 0 — so the user
        # isn't immediately notified about their own post, and isn't shown
        # every prior reply in the thread as "unread" either.
        WatchedThread.objects.get_or_create(
            user=self.request.user, thread=thread,
            defaults={'last_seen_reply_count': thread.reply_count},
        )

        # Fan out FeedItem notifications to thread watchers (excluding the poster).
        # The feed shows these via reason='thread_reply', and the same watcher
        # set feeds the bell (unread count below). Bulk-create for efficiency.
        watchers = WatchedThread.objects.filter(
            thread=thread
        ).exclude(
            user=self.request.user
        ).select_related('user')
        FeedItem.objects.bulk_create([
            FeedItem(user=w.user, thread=thread, post=post, reason='thread_reply')
            for w in watchers
        ], ignore_conflicts=True)

        # Push real-time WebSocket notification to each watcher.
        # Each user has a private group "notifications_{user_id}".
        # We send their current unread count so the bell updates instantly
        # without a separate API call.
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            for w in watchers:
                async_to_sync(channel_layer.group_send)(
                    f"notifications_{w.user.id}",
                    {
                        "type": "send.notification",
                        "unread": w.unread_count,
                        "thread_id": str(thread.id),
                        "thread_title": thread.title,
                        "post_id": str(post.id),
                    }
                )

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def react(self, request, thread_pk=None, pk=None):
        post = self.get_object()
        emoji = request.data.get('emoji')
        existing = Reaction.objects.filter(user=request.user, post=post)
        if existing.filter(emoji=emoji).exists():
            existing.delete()
            return Response({'action': 'removed'})
        existing.delete()
        Reaction.objects.create(user=request.user, post=post, emoji=emoji)
        return Response({'action': 'added'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def report(self, request, thread_pk=None, pk=None):
        post = self.get_object()
        return _create_report(request, post=post)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def edit(self, request, thread_pk=None, pk=None):
        post = self.get_object()
        settings = SiteSettings.get()

        if not settings.allow_post_editing:
            return Response({'error': 'Post editing is disabled on this instance.'}, status=403)

        if post.author_id != request.user.pk:
            return Response({'error': 'You can only edit your own posts.'}, status=403)

        window = settings.post_edit_window_seconds
        if window > 0:
            age = (timezone.now() - post.created_at).total_seconds()
            if age > window:
                return Response({'error': f'Edit window of {window} seconds has expired.'}, status=403)

        new_body = request.data.get('body', '').strip()
        if not new_body:
            return Response({'error': 'Post body cannot be empty.'}, status=400)

        # Check hyperlinks — same rules apply on edit as on create
        from rest_framework.exceptions import ValidationError as _VE
        try:
            _check_links_allowed(settings, post.thread.board, {'body': new_body})
        except _VE as exc:
            return Response(exc.detail, status=400)

        post.body = new_body
        post.edited_at = timezone.now()
        post.edit_count = (post.edit_count or 0) + 1
        post.save(update_fields=['body', 'edited_at', 'edit_count'])

        serializer = self.get_serializer(post)
        return Response(serializer.data)


class ConversationViewSet(viewsets.ViewSet):
    """
    Private messaging. A "conversation" is a Thread with
    is_private_message=True living on the hidden DM system board (see
    get_or_create_dm_board) — see Thread model docstring for why this reuses
    Thread/Post rather than a separate model.

    Sending/listing messages within an existing conversation is NOT handled
    here — that's the ordinary /api/threads/<thread_pk>/posts/ endpoint,
    gated by can_access_private_thread() in PostViewSet. This viewset only
    covers starting a conversation and listing/retrieving your own.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        qs = Thread.objects.filter(
            is_private_message=True, participants=request.user
        ).prefetch_related('participants').order_by('-last_reply_at')
        watch_map = dict(
            WatchedThread.objects.filter(user=request.user, thread__in=qs)
            .values_list('thread_id', 'last_seen_reply_count')
        )
        serializer = ConversationListSerializer(qs, many=True, context={'request': request, 'watch_map': watch_map})
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        # Uses can_access_private_thread (participant OR audited staff
        # override) — deliberately NOT _get_owned_conversation below, which
        # is participant-only. Staff granted the narrow read-only override
        # can view a thread for a legal request; they should never be able
        # to leave it or add/remove participants on someone else's behalf.
        from rest_framework.exceptions import NotFound
        try:
            thread = Thread.objects.prefetch_related('participants').get(pk=pk, is_private_message=True)
        except Thread.DoesNotExist:
            raise NotFound('No conversation matches the given query.')
        if not can_access_private_thread(request.user, thread):
            raise NotFound('No conversation matches the given query.')
        serializer = ConversationDetailSerializer(thread, context={'request': request})
        return Response(serializer.data)

    def create(self, request):
        from rest_framework.exceptions import PermissionDenied, ValidationError

        if not SiteSettings.get().enable_private_messages:
            raise PermissionDenied('Private messages are disabled on this instance.')

        usernames = request.data.get('participants', [])
        if isinstance(usernames, str):
            usernames = [usernames]
        usernames = [u for u in usernames if u and u != request.user.username]
        if not usernames:
            raise ValidationError({'participants': 'At least one other participant is required.'})

        users = list(User.objects.filter(username__in=usernames))
        missing = set(usernames) - {u.username for u in users}
        if missing:
            raise ValidationError({'participants': f'Unknown user(s): {", ".join(sorted(missing))}'})

        body = request.data.get('body', '').strip()
        if not body:
            raise ValidationError({'body': 'An initial message is required to start a conversation.'})

        board = get_or_create_dm_board()
        thread = Thread.objects.create(
            board=board,
            author=request.user,
            title='Private conversation',
            body='',
            is_private_message=True,
        )
        all_participants = [request.user] + users
        thread.participants.add(*all_participants)

        post = Post.objects.create(
            thread=thread, author=request.user, body=body, post_number=1,
            poster_ip=_get_poster_ip(request),
        )
        Thread.objects.filter(pk=thread.pk).update(reply_count=1, last_reply_at=timezone.now())
        thread.refresh_from_db()

        # Auto-watch every participant (not just the sender) so ordinary
        # replies via PostViewSet — which fans out FeedItem + WebSocket
        # notifications to a thread's watchers — notify the whole
        # conversation for free, with no PM-specific notification code.
        for u in all_participants:
            WatchedThread.objects.get_or_create(
                user=u, thread=thread, defaults={'last_seen_reply_count': thread.reply_count}
            )

        User.objects.filter(pk=request.user.pk).update(post_count=F('post_count') + 1)

        serializer = ConversationDetailSerializer(thread, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        thread = self._get_owned_conversation(request, pk)

        thread.participants.remove(request.user)
        WatchedThread.objects.filter(user=request.user, thread=thread).delete()

        # A visible system note in the conversation itself, same as any
        # other message (author=None — same pattern as an anonymous post).
        # Skipped if this emptied the conversation; nobody left to see it.
        if thread.participants.exists():
            Post.objects.create(
                thread=thread, author=None,
                body=f'{request.user.username} left the conversation.',
                post_number=thread.reply_count + 1,
            )
            Thread.objects.filter(pk=thread.pk).update(
                reply_count=F('reply_count') + 1, last_reply_at=timezone.now()
            )

        return Response({'left': True})

    @action(detail=True, methods=['post'], url_path='add-participant')
    def add_participant(self, request, pk=None):
        from rest_framework.exceptions import ValidationError
        thread = self._get_owned_conversation(request, pk)

        if not SiteSettings.get().enable_private_messages:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Private messages are disabled on this instance.')

        username = request.data.get('username', '').strip()
        if not username:
            raise ValidationError({'username': 'This field is required.'})
        try:
            new_participant = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError({'username': f'Unknown user: {username}'})
        if thread.participants.filter(pk=new_participant.pk).exists():
            raise ValidationError({'username': f'{username} is already in this conversation.'})

        thread.participants.add(new_participant)
        # Backdated to the current count, same convention as everywhere
        # else WatchedThread is created — they see new activity from here
        # on, not every prior message retroactively marked unread.
        WatchedThread.objects.get_or_create(
            user=new_participant, thread=thread,
            defaults={'last_seen_reply_count': thread.reply_count},
        )
        Post.objects.create(
            thread=thread, author=None,
            body=f'{request.user.username} added {username} to the conversation.',
            post_number=thread.reply_count + 1,
        )
        Thread.objects.filter(pk=thread.pk).update(
            reply_count=F('reply_count') + 1, last_reply_at=timezone.now()
        )
        thread.refresh_from_db()

        serializer = ConversationDetailSerializer(thread, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='remove-participant')
    def remove_participant(self, request, pk=None):
        from rest_framework.exceptions import ValidationError
        thread = self._get_owned_conversation(request, pk)

        username = request.data.get('username', '').strip()
        if not username:
            raise ValidationError({'username': 'This field is required.'})
        if username == request.user.username:
            raise ValidationError({'username': 'Use the leave endpoint to remove yourself.'})
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            raise ValidationError({'username': f'Unknown user: {username}'})
        if not thread.participants.filter(pk=target.pk).exists():
            raise ValidationError({'username': f'{username} is not in this conversation.'})

        thread.participants.remove(target)
        WatchedThread.objects.filter(user=target, thread=thread).delete()

        if thread.participants.exists():
            Post.objects.create(
                thread=thread, author=None,
                body=f'{request.user.username} removed {username} from the conversation.',
                post_number=thread.reply_count + 1,
            )
            Thread.objects.filter(pk=thread.pk).update(
                reply_count=F('reply_count') + 1, last_reply_at=timezone.now()
            )
            thread.refresh_from_db()

        serializer = ConversationDetailSerializer(thread, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_owned_conversation(self, request, pk):
        """Shared lookup for actions below: must be an existing participant."""
        from rest_framework.exceptions import NotFound
        try:
            thread = Thread.objects.get(pk=pk, is_private_message=True)
        except Thread.DoesNotExist:
            raise NotFound('No conversation matches the given query.')
        if not thread.participants.filter(pk=request.user.pk).exists():
            raise NotFound('No conversation matches the given query.')
        return thread


class FeedView(generics.ListAPIView):
    serializer_class = ThreadListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user

        # Base: exclude private community threads unless member, and always
        # exclude private-message threads — those surface only via
        # ConversationViewSet/WatchedThread notifications, never this feed.
        base_q = Q(community__isnull=True) | Q(community__is_private=False)

        if user.is_authenticated:
            joined = user.communities.values_list('id', flat=True)
            # Include private community threads if member
            base_q = base_q | Q(community__in=joined, community__is_private=True)

            qs = Thread.objects.filter(base_q).exclude(is_private_message=True).select_related('author', 'board', 'community').annotate(
                priority=Case(
                    When(community__in=joined, then=0),
                    default=1,
                    output_field=IntegerField()
                )
            ).order_by('priority', '-last_reply_at').distinct()
        else:
            qs = Thread.objects.filter(base_q).exclude(is_private_message=True).select_related('author', 'board').order_by('-last_reply_at')

        if _nsfw_gate_active() and not _age_gate_passed(self.request):
            qs = qs.exclude(board__nsfw=True)

        qs = _exclude_hidden_and_quarantined(qs, user)

        return qs


def _display_name_eligible_at(user, cooldown_days):
    """
    Returns the datetime a user becomes eligible to change their display name
    again, or None if they're eligible right now (no prior change, or
    cooldown_days is 0).
    """
    if cooldown_days <= 0 or not user.display_name_last_changed_at:
        return None
    eligible_at = user.display_name_last_changed_at + timedelta(days=cooldown_days)
    return eligible_at if eligible_at > timezone.now() else None


class MyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        # Username changes need side effects (cooldown check, audit log
        # write) that don't belong in UserSerializer.update() — that
        # serializer is reused in lots of read-only contexts (reports,
        # post authors, etc.) and shouldn't carry write-path logic
        # specific to this one endpoint.
        new_display_name = request.data.get('display_name')
        user = request.user
        if new_display_name and new_display_name != user.display_name:
            settings_ = SiteSettings.get()
            eligible_at = _display_name_eligible_at(user, settings_.display_name_change_cooldown_days)
            if eligible_at:
                return Response({
                    'error': f'You can change your display name again on '
                             f'{eligible_at.date().isoformat()}.',
                    'eligible_at': eligible_at.isoformat(),
                }, status=429)

            old_display_name = user.display_name
            response = super().update(request, *args, **kwargs)
            if response.status_code < 300:
                user.refresh_from_db()
                # Cooldown timestamp is unconditional — tracked regardless
                # of the audit-log toggle (see User.display_name_last_changed_at
                # docstring and SiteSettings.enable_display_name_change_audit).
                user.display_name_last_changed_at = timezone.now()
                user.save(update_fields=['display_name_last_changed_at'])
                if settings_.enable_display_name_change_audit:
                    DisplayNameChangeLog.objects.create(
                        user=user, old_username=old_username, new_username=user.username,
                    )
            return response

        return super().update(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        user = request.user

        op_threads = Thread.objects.filter(author=user).select_related('board').order_by('-last_reply_at')
        commented_threads = Thread.objects.filter(
            posts__author=user
        ).exclude(author=user).select_related('board').distinct().order_by('-last_reply_at')

        # Memberships with role info
        memberships = Membership.objects.filter(user=user).select_related(
            'community', 'community__board'
        ).order_by('role', 'community__name')

        # Pre-computed so the frontend doesn't duplicate the cooldown-days
        # math from update() above — None means eligible right now (no
        # prior change, or cooldown is 0/disabled).
        eligible_at = _display_name_eligible_at(user, SiteSettings.get().display_name_change_cooldown_days)
        username_eligible_at = eligible_at.isoformat() if eligible_at else None

        return Response({
            'user': UserSerializer(user).data,
            'age_verified': user.age_verified,
            'display_name_eligible_at': username_eligible_at,
            'stats': {
                'op_count': op_threads.count(),
                'commented_count': commented_threads.count(),
                'total_posts': Post.objects.filter(author=user).count(),
                'communities_count': memberships.count(),
                'member_since': user.created_at,
            },
            'op_threads': ThreadListSerializer(op_threads, many=True, context={'request': request}).data,
            'commented_threads': ThreadListSerializer(commented_threads, many=True, context={'request': request}).data,
            'communities': MembershipSerializer(memberships, many=True, context={'request': request}).data,
        })


class AgeConfirmView(generics.GenericAPIView):
    """
    POST /api/me/age-confirm/
    Records that the authenticated user has confirmed they meet the minimum
    age requirement for NSFW board visibility. Persists on the account, so
    it carries across devices/browsers — unlike the logged-out flow, which
    relies on a client-side flag reset every fresh browser/session.

    One-directional by design: this only ever sets age_verified to True.
    There's no unconfirm endpoint — once a user has confirmed, an operator
    can still reverse it directly in admin if ever needed.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.age_verified:
            user.age_verified = True
            user.save(update_fields=['age_verified'])
        return Response({'age_verified': True})


class PasswordChangeView(generics.GenericAPIView):
    """
    POST /api/me/password/
    Body: { current_password, new_password }
    Validates current password before setting the new one.
    Reissues the auth token so this session continues working.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current = request.data.get('current_password', '')
        new = request.data.get('new_password', '')

        if not current or not new:
            return Response(
                {'error': 'current_password and new_password are required.'},
                status=400,
            )
        if len(new) < 8:
            return Response(
                {'error': 'New password must be at least 8 characters.'},
                status=400,
            )
        if not user.check_password(current):
            return Response(
                {'error': 'Current password is incorrect.'},
                status=400,
            )

        user.set_password(new)
        user.save(update_fields=['password'])

        # Reissue token so this session continues working
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        return Response({'token': token.key})


class AvatarUploadView(generics.GenericAPIView):
    """
    POST /api/me/avatar/ — upload or replace the authenticated user's avatar.

    The image passes through the full safety pipeline before being saved:
      1. allow_avatars gate (SiteSettings.allow_avatars)
      2. Size check (SiteSettings.max_avatar_size_kb)
      3. EXIF strip, square-crop, thumbnail (process_avatar)
      4. CSAM checkpoint (scan_image) — mandatory, no toggle
      5. PDQ hash stored on user.avatar_pdq_hash for provider matching
         once a real detector is wired in (see core/csam_detection.py)

    Returns the updated UserSerializer representation on success.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        settings = SiteSettings.get()

        if not settings.allow_avatars:
            return Response(
                {'error': 'Avatar uploads are disabled on this instance.'},
                status=403,
            )

        image_file = request.FILES.get('avatar')
        if not image_file:
            return Response({'error': 'No avatar file provided.'}, status=400)

        max_bytes = settings.max_avatar_size_kb * 1024
        if image_file.size > max_bytes:
            return Response(
                {'error': f'Avatar too large (max {settings.max_avatar_size_kb}KB).'},
                status=400,
            )

        try:
            processed = process_avatar(image_file)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)

        image_bytes = processed.read()

        # CSAM checkpoint — permanent floor, no SiteSettings toggle.
        # Currently always returns NOT_IMPLEMENTED (stub). See
        # core/csam_detection.py for what an operator must wire in.
        scan_result = scan_image(image_bytes)
        if scan_result.is_flagged:
            report_match(scan_result, context={
                'uploader_id': str(request.user.pk),
                'target': 'avatar',
            })
            return Response({'error': 'This image could not be accepted.'}, status=400)

        pdq = compute_perceptual_hash(image_bytes)

        user = request.user
        filename = f"avatar_{user.pk}.webp"
        user.avatar.save(filename, ContentFile(image_bytes), save=False)
        user.avatar_pdq_hash = pdq
        user.save(update_fields=['avatar', 'avatar_pdq_hash'])

        return Response(UserSerializer(user, context={'request': request}).data)


class MyPermissionsView(generics.GenericAPIView):
    """
    What the current user can do, and where. The frontend mod UI uses this
    to decide what to show rather than re-deriving the permission resolver
    client-side — the resolver in core/permissions.py stays the single
    source of truth.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role

        if role is None:
            return Response({
                'role': None,
                'is_admin_tier': False,
                'capabilities': {},
                'assigned_boards': [],
                'community_staff_of': [],
            })

        capabilities = {
            field: getattr(role, field)
            for field in (
                'can_hide', 'can_resolve_reports', 'can_quarantine', 'can_purge',
                'can_lock_threads', 'can_pin_threads', 'can_suspend', 'can_ban', 'can_manage_roles',
                'can_manage_pages',
            )
        }

        if role.is_admin_tier:
            assigned_boards = list(Board.objects.values_list('slug', flat=True))
        else:
            assigned_boards = list(user.board_assignments.values_list('slug', flat=True))

        community_staff_of = list(
            Membership.objects.filter(user=user, role__in=('mod', 'admin'))
            .values_list('community__slug', flat=True)
        )

        return Response({
            'role': role.name,
            'is_admin_tier': role.is_admin_tier,
            'capabilities': capabilities,
            'assigned_boards': assigned_boards,
            'community_staff_of': community_staff_of,
        })


class ModGridPagination(PageNumberPagination):
    """
    Used only by the /mod grid views (queue, quarantine, sanctioned
    users) so the DataGrid's rows-per-page control can actually change
    the page size via ?page_size=. The global DEFAULT_PAGINATION_CLASS
    (facechan/settings.py) stays untouched for every other endpoint —
    no other list view needs or has been reviewed for this.
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100  # hard ceiling regardless of what the client asks for


def _apply_safe_ordering(request, qs, allowed_fields, default):
    """
    Applies ?ordering=field or ?ordering=-field from query params, but only
    against an explicit allowlist — never pass raw query param text into
    order_by() directly, since that can expose ordering by relation paths
    the caller shouldn't be able to probe, or trigger expensive joins.
    Falls back to `default` (already a valid order_by argument) if the
    requested field isn't in the allowlist or wasn't provided.
    """
    ordering = request.query_params.get('ordering', '')
    field = ordering.lstrip('-')
    if field in allowed_fields:
        return qs.order_by(ordering)
    return qs.order_by(default)




# ── Public profile view ───────────────────────────────────────────────────────

class PublicProfileView(generics.GenericAPIView):
    """
    GET /api/users/:username/ — minimal public profile.

    Returns only what a visitor should see:
    - Avatar initial / avatar image
    - Username + badge
    - Activity tier (derived from post_count, never the raw count)
    - Member since date

    No post history, no communities, no bio, no way to enumerate activity.
    If the user doesn't exist, returns 404.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('User not found.')

        return Response({
            'username': user.username,
            'display_badge': user.display_badge,
            'is_premium': user.is_premium,
            'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None,
            'activity_tier': ActivityTier.for_user(user.post_count),
            'member_since': user.created_at,
        })


# ── Watch thread views ────────────────────────────────────────────────────────

class ThreadWatchView(generics.GenericAPIView):
    """
    POST /api/threads/{id}/watch/ — toggle watch on/off.

    Returns:
        {watching: bool, unread: int, watcher_count: int}

    Also marks last_seen_reply_count to the current reply count when watching,
    so the user starts with zero unread (they're clearly reading the thread now).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        thread = Thread.objects.get(pk=pk)
        watch, created = WatchedThread.objects.get_or_create(
            user=request.user, thread=thread,
            defaults={'last_seen_reply_count': thread.reply_count}
        )
        if not created:
            # Already watching — unwatch
            watch.delete()
            return Response({
                'watching': False,
                'unread': 0,
                'watcher_count': thread.watchers.count(),
            })
        return Response({
            'watching': True,
            'unread': 0,  # just started watching, starts clean
            'watcher_count': thread.watchers.count(),
        })


class ThreadMarkSeenView(generics.GenericAPIView):
    """
    POST /api/threads/{id}/mark-seen/ — update last_seen_reply_count to now.

    Called when the user opens a thread detail page. Clears the unread count
    so the bell badge resets. No-op if the user isn't watching.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        thread = Thread.objects.get(pk=pk)
        WatchedThread.objects.filter(
            user=request.user, thread=thread
        ).update(last_seen_reply_count=thread.reply_count)
        return Response({'ok': True})


class WatchedThreadListView(generics.ListAPIView):
    """
    GET /api/me/watched/ — watched threads with unread counts.

    Data source for the "Watched" tab in /feed and the notification bell
    badge. Returns threads the user is watching, annotated with unread
    reply count. Ordered by most recent activity first.

    A user starts watching a thread automatically when they create it or
    reply to it (see ThreadViewSet/PostViewSet perform_create) — there's
    no separate "watch" button click required to get notified on your own
    threads/replies.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Private-message conversations are deliberately excluded here even
        # though the user is watching them too (see ConversationViewSet.create) —
        # this list feeds the public "Watched threads" tab, which links to
        # /thread/:id and would 404 for a private thread (ThreadViewSet
        # excludes them). Conversations get their own inbox UI instead.
        # The unread COUNT below (NotificationUnreadCountView) intentionally
        # keeps summing across everything, DMs included — one bell for both.
        watches = WatchedThread.objects.filter(
            user=request.user, thread__is_private_message=False
        ).select_related('thread', 'thread__board', 'thread__author').order_by('-thread__last_reply_at')

        return Response([{
            'thread_id': str(w.thread_id),
            'title': w.thread.title,
            'board_slug': w.thread.board.slug,
            'reply_count': w.thread.reply_count,
            'unread': w.unread_count,
            'last_reply_at': w.thread.last_reply_at,
        } for w in watches])


class NotificationUnreadCountView(generics.GenericAPIView):
    """
    GET /api/me/notifications/unread-count/ — total unread notifications.

    Returns a single integer — the sum of unread replies across all watched
    threads. Polled by NotificationContext.jsx as a fallback when the
    WebSocket notification channel is unavailable. Zero cost to compute.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        watches = WatchedThread.objects.filter(
            user=request.user
        ).select_related('thread')
        total = sum(w.unread_count for w in watches)
        return Response({'unread': total})


class ModQueueView(generics.ListAPIView):
    """
    The moderation queue. Scoped to what the requester can actually act
    on — a board-scoped janitor only sees reports for content on their
    assigned boards; admin-tier sees everything; a community mod sees
    reports for their community's content even if they hold no site role
    at all. Mirrors the scoping in core/permissions.py exactly, since a
    report a user can't act on shouldn't show up in their queue.

    Supports ?ordering=created_at|-created_at|status|-status|reason|-reason
    for the grid view's sortable columns; defaults to -created_at (newest
    first) when absent or not in the allowlist.
    """
    serializer_class = ModReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ModGridPagination
    ORDERING_FIELDS = {'created_at', 'updated_at', 'status', 'reason'}

    def get_queryset(self):
        user = self.request.user
        role = user.role

        status_filter = self.request.query_params.get('status', 'open')
        qs = Report.objects.select_related(
            'reporter', 'resolved_by', 'thread', 'thread__board',
            'post', 'post__thread', 'post__thread__board'
        )
        qs = _apply_safe_ordering(self.request, qs, self.ORDERING_FIELDS, '-created_at')

        if status_filter != 'all':
            qs = qs.filter(status=status_filter)

        if role and role.is_admin_tier and role.can_resolve_reports:
            return qs  # unscoped

        allowed_board_ids = set()
        if role and role.can_resolve_reports:
            allowed_board_ids = set(user.board_assignments.values_list('pk', flat=True))

        allowed_community_ids = set(
            Membership.objects.filter(user=user, role__in=('mod', 'admin'))
            .values_list('community_id', flat=True)
        )

        if not allowed_board_ids and not allowed_community_ids:
            return qs.none()

        return qs.filter(
            Q(thread__board_id__in=allowed_board_ids) |
            Q(post__thread__board_id__in=allowed_board_ids) |
            Q(thread__community_id__in=allowed_community_ids) |
            Q(post__thread__community_id__in=allowed_community_ids)
        ).distinct()


class ModResolveReportView(generics.GenericAPIView):
    """
    Resolve a report by taking an action on the underlying content.

    action: 'dismiss' | 'hide' | 'unhide' | 'quarantine' | 'purge'
    - dismiss: report -> dismissed, content untouched
    - hide: report -> actioned, content hidden (reversible, visible to
      author/staff — tier 1)
    - unhide: reverses 'hide'. Checked against the content's actual
      is_hidden state, not report.status — a report sits at status
      'actioned' for hide/quarantine/purge alike, so status alone can't
      tell us whether unhide is the right reversal. Same capability as
      hide (can_hide) governs both directions. Report stays 'actioned'
      either way; this isn't a new report outcome, just a state flip on
      content that a report happened to point at — same content can be
      hidden and unhidden repeatedly without spawning new report rows.
    - quarantine: report -> actioned, content invisible to EVERYONE
      including its author, pending an admin decision (reversible by an
      admin, see ModQuarantineActionView — tier 2, board-admin and above)
    - purge: report -> actioned, content permanently deleted. IRREVERSIBLE.
      Admin-tier only, hard-enforced via can_purge_content() regardless of
      the can_purge flag value (tier 3)

    See COMPLIANCE.md for why purge isn't the default/only option — some
    content (e.g. anything that might be evidentiary) may need to be
    retained rather than destroyed by a single moderation action, and
    what's actually required there varies by jurisdiction and needs real
    legal advice, not just this tiering.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        # select_related is load-bearing here, not just an optimisation:
        # it caches report.thread/report.post on this Python instance
        # BEFORE any purge can run, so the serializer below can still show
        # a preview of what was purged even though the underlying row is
        # gone from the DB by the time we respond. Don't remove it without
        # checking the purge branch still works.
        try:
            report = Report.objects.select_related('thread', 'post', 'post__thread').get(pk=pk)
        except Report.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('No Report matches the given query.')

        target = report.target
        if target is None:
            return Response({'error': 'The reported content no longer exists.'}, status=400)

        action = request.data.get('action')
        note = request.data.get('resolution_note', '')[:1000]

        if action == 'dismiss':
            if not can_moderate(request.user, target, 'can_resolve_reports'):
                return Response({'error': 'You do not have permission to resolve this report.'}, status=403)
            report.status = 'dismissed'
            report.resolved_by = request.user
            report.resolution_note = note
            report.save(update_fields=['status', 'resolved_by', 'resolution_note', 'updated_at'])

        elif action == 'hide':
            if not can_moderate(request.user, target, 'can_hide'):
                return Response({'error': 'You do not have permission to hide this content.'}, status=403)
            hide_content(target, by_user=request.user, reason=note or f'Report: {report.get_reason_display()}')
            report.status = 'actioned'
            report.resolved_by = request.user
            report.resolution_note = note
            report.save(update_fields=['status', 'resolved_by', 'resolution_note', 'updated_at'])

        elif action == 'unhide':
            if not can_moderate(request.user, target, 'can_hide'):
                return Response({'error': 'You do not have permission to unhide this content.'}, status=403)
            if not target.is_hidden:
                return Response({'error': 'This content is not currently hidden.'}, status=400)
            unhide_content(target)
            # Resolution note/resolved_by updated to reflect the reversal,
            # but status stays 'actioned' — unhiding doesn't reopen the
            # report or invent a new status value for it.
            report.resolved_by = request.user
            report.resolution_note = note or report.resolution_note
            report.save(update_fields=['resolved_by', 'resolution_note', 'updated_at'])

        elif action == 'quarantine':
            if not can_moderate(request.user, target, 'can_quarantine'):
                return Response({'error': 'You do not have permission to quarantine this content.'}, status=403)
            quarantine_content(target, by_user=request.user, reason=note or f'Report: {report.get_reason_display()}')
            report.status = 'actioned'
            report.resolved_by = request.user
            report.resolution_note = note
            report.save(update_fields=['status', 'resolved_by', 'resolution_note', 'updated_at'])

        elif action == 'purge':
            if not can_purge_content(request.user):
                return Response({'error': 'Purging is restricted to admins.'}, status=403)
            # Save the report's resolution BEFORE deleting the target — once
            # purge_content() runs, report.thread/report.post point at a
            # deleted row and Django refuses to save a model with a
            # dangling FK to an unsaved/gone related object. Resolving the
            # report first also means we keep a record even if something
            # went wrong with the delete itself.
            report.status = 'actioned'
            report.resolved_by = request.user
            report.resolution_note = note
            report.save(update_fields=['status', 'resolved_by', 'resolution_note', 'updated_at'])
            purge_content(target)
            return Response(ModReportSerializer(report).data)

        else:
            return Response({'error': "action must be one of: dismiss, hide, unhide, quarantine, purge"}, status=400)

        return Response(ModReportSerializer(report).data)


class ModUserActionView(generics.GenericAPIView):
    """
    Suspend or ban a user. Both are site-staff-only capabilities — there's
    no content to scope against here, so this checks the requester's site
    role directly rather than going through can_moderate (which always
    needs a Thread/Post to resolve board/community scope against).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id=None):
        role = request.user.role
        if role is None:
            return Response({'error': 'You do not have a staff role.'}, status=403)

        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('No User matches the given query.')

        action = request.data.get('action')

        if action == 'suspend':
            if not role.can_suspend:
                return Response({'error': 'You do not have permission to suspend users.'}, status=403)
            hours = request.data.get('hours')
            try:
                hours = float(hours)
                if hours <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                return Response({'error': 'hours must be a positive number.'}, status=400)
            target_user.suspended_until = timezone.now() + timedelta(hours=hours)
            target_user.save(update_fields=['suspended_until'])

        elif action == 'unsuspend':
            if not role.can_suspend:
                return Response({'error': 'You do not have permission to manage suspensions.'}, status=403)
            target_user.suspended_until = None
            target_user.save(update_fields=['suspended_until'])

        elif action == 'ban':
            if not role.can_ban:
                return Response({'error': 'You do not have permission to ban users.'}, status=403)
            target_user.is_banned = True
            target_user.save(update_fields=['is_banned'])

        elif action == 'unban':
            if not role.can_ban:
                return Response({'error': 'You do not have permission to manage bans.'}, status=403)
            target_user.is_banned = False
            target_user.save(update_fields=['is_banned'])

        else:
            return Response({'error': 'action must be one of: suspend, unsuspend, ban, unban'}, status=400)

        return Response(UserSerializer(target_user).data)


class ModSanctionedUsersView(generics.ListAPIView):
    """
    Lists currently-sanctioned users (banned OR actively suspended) — the
    list backing ModUsers' grid/card view. Deliberately NOT a general user
    search endpoint: it only ever returns accounts already under a
    sanction, which is a much narrower and more clearly-justified data
    exposure than "look up any user by name" (a decision Ed and Claude
    discussed and intentionally avoided building when target_author_id
    click-through was added instead). Gated on can_suspend or can_ban,
    matching ModLayout's sidebar visibility logic for this page.
    """
    serializer_class = SanctionedUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ModGridPagination
    ORDERING_FIELDS = {'username', 'is_banned', 'suspended_until', 'created_at'}

    def get_queryset(self):
        role = self.request.user.role
        if not (role and (role.can_suspend or role.can_ban)):
            return User.objects.none()
        qs = User.objects.filter(
            Q(is_banned=True) | Q(suspended_until__gt=timezone.now())
        )
        return _apply_safe_ordering(self.request, qs, self.ORDERING_FIELDS, '-suspended_until')


class ModQuarantineQueueView(generics.ListAPIView):
    """
    Admin-only. Lists everything currently quarantined, across every
    board/community — quarantine review is an admin-tier concept (see
    Role.can_quarantine docstring), not board-scoped like the main mod
    queue, since it's specifically "pending an admin decision."

    Supports ?ordering= the same way ModQueueView does.
    """
    serializer_class = ModReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ModGridPagination
    ORDERING_FIELDS = {'created_at', 'updated_at', 'status', 'reason'}

    def get_queryset(self):
        user = self.request.user
        if not (user.role and user.role.is_admin_tier):
            return Report.objects.none()
        # Reuse ModReportSerializer's shape by finding the reports that
        # led to quarantine, rather than inventing a parallel serializer
        # for raw Thread/Post — keeps the queue UI consistent either way.
        qs = Report.objects.filter(
            Q(thread__is_quarantined=True) | Q(post__is_quarantined=True)
        ).select_related(
            'reporter', 'resolved_by', 'thread', 'thread__board',
            'post', 'post__thread', 'post__thread__board'
        )
        return _apply_safe_ordering(self.request, qs, self.ORDERING_FIELDS, '-created_at')


class ModQuarantineActionView(generics.GenericAPIView):
    """
    Admin-only. Resolve something already in quarantine: restore (back to
    fully visible, clears quarantine fields) or purge (permanent delete).
    Separate from ModResolveReportView's 'quarantine'/'purge' actions,
    which act via a specific report — this acts directly on content that
    may have ended up quarantined through any path, for admins reviewing
    the quarantine queue itself rather than a single report.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, content_type=None, content_id=None):
        if content_type not in ('thread', 'post'):
            return Response({'error': "content_type must be 'thread' or 'post'."}, status=400)

        model = Thread if content_type == 'thread' else Post
        try:
            target = model.objects.get(pk=content_id)
        except model.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound(f'No {content_type} matches the given query.')

        action = request.data.get('action')

        if action == 'restore':
            if not (request.user.role and request.user.role.is_admin_tier):
                return Response({'error': 'Restoring from quarantine is restricted to admins.'}, status=403)
            restore_from_quarantine(target)

        elif action == 'purge':
            if not can_purge_content(request.user):
                return Response({'error': 'Purging is restricted to admins.'}, status=403)
            purge_content(target)
            return Response({'purged': True})

        else:
            return Response({'error': "action must be one of: restore, purge"}, status=400)

        return Response({'is_quarantined': target.is_quarantined})
