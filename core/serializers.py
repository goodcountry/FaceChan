from rest_framework import serializers
from django.db.models import Q
from .models import User, Board, Community, Membership, Thread, Post, Reaction, SiteSettings, Report, CommunityInvite, SitePage


class SitePageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SitePage
        fields = ['slug', 'title', 'content', 'updated_at']
        read_only_fields = ['slug', 'updated_at']


class SitePageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SitePage
        fields = ['slug', 'title', 'display_order']

def _visible_to(qs, request):
    """
    Exclude hidden posts/replies except the requester's own, and
    quarantined ones for EVERYONE including the author — quarantine is a
    stronger removal than hide, by design (see core/permissions.py).
    Staff review hidden/quarantined content via the moderation queue, not
    by it appearing inline in ordinary thread views just because they
    hold a staff role.
    """
    qs = qs.filter(is_quarantined=False)
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return qs.filter(Q(is_hidden=False) | Q(author=user))
    return qs.filter(is_hidden=False)


class SiteSettingsSerializer(serializers.ModelSerializer):
    mcaptcha_enabled = serializers.SerializerMethodField()
    mcaptcha_url = serializers.SerializerMethodField()
    mcaptcha_site_key = serializers.SerializerMethodField()

    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'site_tagline',
            'max_threads_per_board', 'max_threads_per_user_per_day',
            'max_posts_per_thread', 'max_post_length', 'max_posts_per_user_per_day',
            'bump_lock_percent',
            'max_communities', 'max_communities_per_user',
            'allow_image_uploads', 'max_image_size_mb',
            'allow_avatars', 'max_avatar_size_kb',
            'allow_video_uploads', 'max_video_size_mb', 'max_video_duration_seconds',
            'registration_open', 'require_email', 'enable_communities', 'allow_markdown',
            'allow_post_editing', 'post_edit_window_seconds',
            'enable_nsfw_boards', 'allow_anonymous_posts', 'display_name_change_cooldown_days',
            'jurisdiction_mode', 'enable_content_reporting',
            'require_age_confirmation', 'minimum_age',
            'block_nsfw_without_age_gate', 'publish_transparency_info',
            'moderation_contact',
            'mcaptcha_enabled', 'mcaptcha_url', 'mcaptcha_site_key',
        ]

    def get_mcaptcha_enabled(self, obj):
        from .captcha import mcaptcha_configured
        return mcaptcha_configured()

    def get_mcaptcha_url(self, obj):
        from django.conf import settings
        return getattr(settings, 'MCAPTCHA_URL', '') or ''

    def get_mcaptcha_site_key(self, obj):
        from django.conf import settings
        return getattr(settings, 'MCAPTCHA_SITE_KEY', '') or ''


class ReportSerializer(serializers.ModelSerializer):
    """Used for creating a report — reporter/target are set server-side."""
    class Meta:
        model = Report
        fields = ['id', 'reason', 'details', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    communities_created = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'avatar', 'bio', 'tagline', 'display_badge',
                  'post_count', 'is_premium', 'communities_created', 'created_at']
        read_only_fields = ['username', 'post_count', 'created_at']

    def get_communities_created(self, obj):
        from .models import Community
        return Community.objects.filter(created_by=obj).count()


class SanctionedUserSerializer(serializers.ModelSerializer):
    """
    For the sanctioned-users list (ModSanctionedUsersView) only.
    Deliberately separate from UserSerializer — is_banned/suspended_until
    aren't appropriate to expose wherever a generic user object shows up
    (report listings, post authors, etc.), only here where the viewer has
    already been confirmed to hold can_suspend or can_ban.
    """
    is_suspended = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'is_banned', 'suspended_until', 'is_suspended', 'created_at']


class ModReportSerializer(serializers.ModelSerializer):
    """
    Full-context view of a report for the moderation queue. Unlike
    ReportSerializer (used for the reporting flow itself), this exposes
    the reporter's identity and the actual reported content — appropriate
    here since only staff with reach over the content ever see this.
    """
    reporter = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.SerializerMethodField()
    target_preview = serializers.SerializerMethodField()
    target_author = serializers.SerializerMethodField()
    target_author_id = serializers.SerializerMethodField()
    target_is_hidden = serializers.SerializerMethodField()
    target_is_quarantined = serializers.SerializerMethodField()
    board_slug = serializers.SerializerMethodField()
    thread_id = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'reporter', 'reason', 'details', 'status',
            'resolved_by', 'resolution_note', 'created_at', 'updated_at',
            'target_type', 'target_id', 'target_preview', 'target_author',
            'target_author_id', 'target_is_hidden', 'target_is_quarantined',
            'board_slug', 'thread_id',
        ]
        read_only_fields = fields

    def get_target_type(self, obj):
        # Was: 'thread' if obj.thread_id else 'post' — broke the moment a
        # thread report got purged, since thread_id goes NULL too and this
        # silently mislabeled it as a post report. target_type is now
        # stored explicitly at creation and never inferred from a relation
        # that can disappear. Older pre-migration rows may have it null;
        # thread_id/post_id are still a safe fallback for THOSE specifically
        # because they haven't been purged since (this code is the fix).
        if obj.target_type:
            return obj.target_type
        return 'thread' if obj.thread_id else 'post'

    def get_target_id(self, obj):
        target = obj.target
        return target.pk if target else None

    def get_target_preview(self, obj):
        # Prefer the live target so an edited/updated preview stays
        # current while the content exists; fall back to the snapshot
        # taken at report-filing time once it's gone.
        target = obj.target
        if target is not None:
            text = target.title if obj.thread_id else target.body
            return text[:200]
        if obj.target_preview_snapshot:
            return obj.target_preview_snapshot
        return '(content deleted)'

    def get_target_author(self, obj):
        target = obj.target
        if target is not None and target.author is not None:
            return target.author.username
        # Snapshot survives even past a User account being deleted
        # outright, not just the content being purged.
        return obj.target_author_username or None

    def get_target_author_id(self, obj):
        target = obj.target
        if target is not None and target.author is not None:
            return target.author.pk
        return obj.target_author_id

    def get_target_is_hidden(self, obj):
        target = obj.target
        return bool(target and target.is_hidden)

    def get_target_is_quarantined(self, obj):
        target = obj.target
        return bool(target and target.is_quarantined)

    def get_board_slug(self, obj):
        target = obj.target
        if target is not None:
            return target.board.slug if obj.thread_id else target.thread.board.slug
        return obj.target_board_slug or None

    def get_thread_id(self, obj):
        if obj.thread_id:
            return obj.thread_id
        if obj.post_id and obj.post:
            return obj.post.thread_id
        return None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    age_confirmed = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'age_confirmed']
        extra_kwargs = {'email': {'required': False}}

    def validate(self, attrs):
        from .models import SiteSettings
        settings = SiteSettings.get()
        if settings.require_age_confirmation and not attrs.get('age_confirmed'):
            raise serializers.ValidationError({
                'age_confirmed': f'You must confirm you are at least {settings.minimum_age} '
                                  f'years old to register on this instance.'
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('age_confirmed', None)
        user = User.objects.create_user(**validated_data)
        # Default display name to username — user can change it immediately
        user.display_name = user.username
        user.save(update_fields=['display_name'])
        return user


class BoardSerializer(serializers.ModelSerializer):
    thread_count = serializers.SerializerMethodField()

    class Meta:
        model = Board
        fields = ['slug', 'name', 'description', 'icon', 'nsfw', 'allow_images', 'allow_videos', 'allow_video_sound', 'thread_count']

    def get_thread_count(self, obj):
        return obj.threads.count()


class MembershipSerializer(serializers.ModelSerializer):
    """Community with the user's role — used in profile."""
    id = serializers.CharField(source='community.id')
    name = serializers.CharField(source='community.name')
    slug = serializers.CharField(source='community.slug')
    board_slug = serializers.CharField(source='community.board.slug', read_only=True)
    board_icon = serializers.CharField(source='community.board.icon', read_only=True)
    is_private = serializers.BooleanField(source='community.is_private')
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ['id', 'name', 'slug', 'board_slug', 'board_icon',
                  'is_private', 'role', 'member_count', 'joined_at']

    def get_member_count(self, obj):
        return obj.community.members.count()


class MemberRosterSerializer(serializers.ModelSerializer):
    """User + role info — used for the /communities/<slug>/members/ endpoint."""
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['user', 'role', 'joined_at']


class CommunitySerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    board_slug = serializers.CharField(source='board.slug', read_only=True)
    board_icon = serializers.CharField(source='board.icon', read_only=True)
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    created_by_id = serializers.UUIDField(source='created_by.id', read_only=True)
    active_posts = serializers.IntegerField(read_only=True, default=0)
    trending_posts = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Community
        fields = ['id', 'name', 'slug', 'description', 'banner', 'board_slug',
                  'board_icon', 'is_private', 'member_count', 'is_member', 'user_role',
                  'created_by_id', 'active_posts', 'trending_posts', 'created_at']
        read_only_fields = ['created_at']

    def get_member_count(self, obj):
        if hasattr(obj, 'member_count') and obj.member_count is not None:
            return obj.member_count
        return obj.members.count()

    def get_is_member(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.members.filter(pk=request.user.pk).exists()
        return False

    def get_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = Membership.objects.filter(user=request.user, community=obj).first()
            return membership.role if membership else None
        return None


class CommunityDetailSerializer(CommunitySerializer):
    """Full community detail including recent thread count and board info."""
    thread_count = serializers.SerializerMethodField()
    board_name = serializers.CharField(source='board.name', read_only=True)

    class Meta(CommunitySerializer.Meta):
        fields = CommunitySerializer.Meta.fields + ['thread_count', 'board_name']

    def get_thread_count(self, obj):
        return obj.threads.count()


def get_reaction_summary(obj, user):
    from django.db.models import Count
    qs = obj.reactions.values('emoji').annotate(count=Count('id'))
    user_reacted = set()
    if user and user.is_authenticated:
        user_reacted = set(obj.reactions.filter(user=user).values_list('emoji', flat=True))
    return [{'emoji': r['emoji'], 'count': r['count'], 'reacted': r['emoji'] in user_reacted} for r in qs]


class ReplySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'author', 'body', 'image', 'thumbnail', 'video', 'video_thumbnail', 'video_duration', 'sage', 'is_hidden', 'reactions', 'reply_count', 'created_at', 'edited_at', 'edit_count']

    def get_reactions(self, obj):
        return get_reaction_summary(obj, self.context.get('request') and self.context['request'].user)

    def get_reply_count(self, obj):
        return obj.replies.count()

    def to_representation(self, instance):
        from .word_filter import apply_word_filters
        data = super().to_representation(instance)
        board_slug = instance.thread.board.slug if instance.thread_id else None
        data['body'] = apply_word_filters(data.get('body', ''), board_slug)
        return data


class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    parent_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'body', 'image',
            'video', 'video_thumbnail', 'video_duration',
            'parent_id', 'post_number', 'sage', 'is_hidden',
            'reactions', 'replies', 'reply_count',
            'created_at', 'edited_at', 'edit_count'
        ]
        read_only_fields = ['post_number', 'author', 'reactions', 'replies', 'reply_count']

    def get_reactions(self, obj):
        return get_reaction_summary(obj, self.context.get('request') and self.context['request'].user)

    def get_replies(self, obj):
        if obj.parent_id is not None:
            return []
        qs = obj.replies.select_related('author').prefetch_related('reactions').order_by('created_at')
        qs = _visible_to(qs, self.context.get('request'))
        return ReplySerializer(qs, many=True, context=self.context).data

    def get_reply_count(self, obj):
        return obj.replies.count()

    def to_representation(self, instance):
        from .word_filter import apply_word_filters
        data = super().to_representation(instance)
        board_slug = instance.thread.board.slug if instance.thread_id else None
        data['body'] = apply_word_filters(data.get('body', ''), board_slug)
        return data


class ThreadListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    board_slug = serializers.CharField(source='board.slug', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)
    community_slug = serializers.CharField(source='community.slug', read_only=True)
    reactions = serializers.SerializerMethodField()
    reaction_count = serializers.SerializerMethodField()
    allow_images = serializers.BooleanField(source='board.allow_images', read_only=True)
    allow_videos = serializers.BooleanField(source='board.allow_videos', read_only=True)
    allow_video_sound = serializers.BooleanField(source='board.allow_video_sound', read_only=True)

    class Meta:
        model = Thread
        fields = ['id', 'board_slug', 'community_name', 'community_slug',
                  'author', 'title', 'body', 'image', 'thumbnail',
                  'video', 'video_thumbnail', 'video_duration',
                  'is_pinned', 'is_locked', 'is_hidden', 'comments_disabled', 'reply_count', 'view_count',
                  'reactions', 'reaction_count', 'last_reply_at', 'created_at',
                  'allow_images', 'allow_videos', 'allow_video_sound']

    def get_reactions(self, obj):
        return get_reaction_summary(obj, self.context.get('request') and self.context['request'].user)

    def get_reaction_count(self, obj):
        return obj.reactions.count()

    def to_representation(self, instance):
        from .word_filter import apply_word_filters
        data = super().to_representation(instance)
        board_slug = data.get('board_slug')
        data['title'] = apply_word_filters(data.get('title', ''), board_slug)
        data['body'] = apply_word_filters(data.get('body', ''), board_slug)
        return data


class ThreadDetailSerializer(ThreadListSerializer):
    posts = serializers.SerializerMethodField()
    watcher_count = serializers.SerializerMethodField()

    class Meta(ThreadListSerializer.Meta):
        fields = ThreadListSerializer.Meta.fields + ['posts', 'watcher_count']

    def get_posts(self, obj):
        qs = obj.posts.filter(parent__isnull=True).select_related('author', 'thread__board').prefetch_related(
            'reactions', 'replies__author', 'replies__reactions', 'replies__thread__board'
        ).order_by('created_at')
        qs = _visible_to(qs, self.context.get('request'))
        return PostSerializer(qs, many=True, context=self.context).data

    def get_watcher_count(self, obj):
        return obj.watchers.count()

class CommunityInviteSerializer(serializers.ModelSerializer):
    """Returned to admins/mods managing invites for their community."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    is_valid = serializers.SerializerMethodField()
    invite_url = serializers.SerializerMethodField()

    class Meta:
        model = CommunityInvite
        fields = [
            'id', 'token', 'created_by_username', 'created_at',
            'expires_at', 'max_uses', 'use_count', 'is_active', 'is_valid',
            'invite_url',
        ]
        read_only_fields = ['id', 'token', 'created_by_username', 'created_at', 'use_count']

    def get_is_valid(self, obj):
        return obj.is_valid()

    def get_invite_url(self, obj):
        request = self.context.get('request')
        path = f'/invite/{obj.token}'
        if request:
            return request.build_absolute_uri(path)
        return path


class CommunityInvitePreviewSerializer(serializers.ModelSerializer):
    """Public-facing: community info shown on the invite landing page."""
    community_name = serializers.CharField(source='community.name')
    community_slug = serializers.CharField(source='community.slug')
    community_description = serializers.CharField(source='community.description')
    community_icon = serializers.CharField(source='community.board.icon', default='👥')
    member_count = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = CommunityInvite
        fields = [
            'token', 'community_name', 'community_slug', 'community_description',
            'community_icon', 'member_count', 'is_valid', 'expires_at', 'max_uses', 'use_count',
        ]

    def get_member_count(self, obj):
        return obj.community.members.count()

    def get_is_valid(self, obj):
        return obj.is_valid()
