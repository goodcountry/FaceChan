from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import User, Board, Community, Membership, Thread, Post, Reaction, FeedItem, SiteSettings, Report, Role, DisplayNameChangeLog, ActivityTier, CommunityInvite, WordFilter, SitePage


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Site owner defines exactly what each staff tier can do here. is_admin_tier
    roles are unscoped (every board/community) and are the only roles that
    can manage other roles/assignments — keep that list short.
    """
    list_display = ['name', 'tier', 'is_admin_tier', 'user_count',
                     'can_hide', 'can_resolve_reports', 'can_quarantine', 'can_purge',
                     'can_lock_threads', 'can_pin_threads', 'can_suspend', 'can_ban', 'can_manage_roles', 'can_manage_pages']
    list_filter = ['is_admin_tier']
    search_fields = ['name']
    ordering = ['-tier']

    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Users'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'role', 'is_premium', 'can_post_media', 'age_verified', 'post_count',
                     'is_banned', 'is_suspended_display', 'is_staff', 'created_at']
    list_filter = ['role', 'is_premium', 'can_post_media', 'age_verified', 'is_banned', 'is_staff', 'is_active']
    search_fields = ['username', 'email']
    ordering = ['-created_at']
    autocomplete_fields = ['role']
    readonly_fields = BaseUserAdmin.readonly_fields + ('display_name_last_changed_at',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('FaceChan', {'fields': ('avatar', 'bio', 'tagline', 'display_badge', 'post_count', 'is_premium')}),
        ('Staff role', {
            'fields': ('role', 'board_assignments'),
            'description': 'board_assignments is ignored for admin-tier roles — those are '
                            'unscoped regardless of what boards are listed here.'
        }),
        ('Sanctions', {'fields': ('is_banned', 'suspended_until')}),
        ('Media posting', {
            'fields': ('can_post_media',),
            'description': 'Grant this user the ability to attach images and videos even '
                            'when site-wide media uploads are disabled. Operator-only — '
                            'no equivalent exists in the mod panel.'
        }),
        ('Age verification', {
            'fields': ('age_verified',),
            'description': 'Whether this user has confirmed they meet the minimum age '
                            'requirement to view NSFW boards. Persists across devices once '
                            'set — normally set by the user themselves via the age '
                            'confirmation prompt, settable here directly by an operator.'
        }),
        ('Username history', {
            'fields': ('display_name_last_changed_at',),
            'description': 'Read-only — set automatically when the user changes their own '
                            'username via the API. See DisplayNameChangeLog for the full history '
                            '(old name, new name) when SiteSettings.enable_display_name_change_audit is on.'
        }),
    )
    filter_horizontal = BaseUserAdmin.filter_horizontal + ('board_assignments',)

    def is_suspended_display(self, obj):
        return obj.is_suspended
    is_suspended_display.short_description = 'Suspended'
    is_suspended_display.boolean = True


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name', 'icon', 'nsfw', 'allow_images', 'thread_count', 'created_at']
    list_editable = ['allow_images']
    search_fields = ['slug', 'name']
    prepopulated_fields = {'slug': ('name',)}

    def thread_count(self, obj):
        return obj.threads.count()
    thread_count.short_description = 'Threads'


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1
    autocomplete_fields = ['user']


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'board', 'is_private', 'member_count', 'created_by', 'created_at']
    list_filter = ['is_private', 'board']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['created_by', 'board']
    inlines = [MembershipInline]

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'community', 'role', 'joined_at']
    list_filter = ['role', 'community']
    search_fields = ['user__username', 'community__name']
    autocomplete_fields = ['user', 'community']


class PostInline(admin.TabularInline):
    model = Post
    extra = 0
    readonly_fields = ['author', 'body', 'post_number', 'sage', 'created_at', 'poster_ip']
    can_delete = True
    max_num = 0  # no adding posts via inline
    fields = ['author', 'body', 'post_number', 'sage', 'created_at', 'poster_ip']


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'board', 'community', 'author', 'poster_ip', 'reply_count',
                    'view_count', 'is_pinned', 'comments_disabled', 'is_locked', 'is_hidden', 'is_quarantined', 'last_reply_at']
    list_filter = ['board', 'is_pinned', 'comments_disabled', 'is_locked', 'is_hidden', 'is_quarantined', 'community']
    search_fields = ['title', 'body', 'author__username']
    readonly_fields = ['reply_count', 'view_count', 'last_reply_at', 'created_at',
                        'hidden_by', 'hidden_at', 'quarantined_by', 'quarantined_at',
                        'poster_ip']
    list_editable = ['is_pinned', 'comments_disabled', 'is_locked']
    inlines = [PostInline]
    ordering = ['-last_reply_at']

    actions = ['lock_threads', 'unlock_threads', 'pin_threads', 'unpin_threads',
               'hide_threads', 'unhide_threads', 'quarantine_threads',
               'restore_threads', 'purge_threads']

    def lock_threads(self, request, queryset):
        queryset.update(is_locked=True)
    lock_threads.short_description = 'Lock selected threads'

    def unlock_threads(self, request, queryset):
        queryset.update(is_locked=False)
    unlock_threads.short_description = 'Unlock selected threads'

    def pin_threads(self, request, queryset):
        queryset.update(is_pinned=True, comments_disabled=True)
    pin_threads.short_description = 'Pin selected threads'

    def unpin_threads(self, request, queryset):
        queryset.update(is_pinned=False, comments_disabled=False)
    unpin_threads.short_description = 'Unpin selected threads'

    def hide_threads(self, request, queryset):
        from .permissions import hide_content
        for thread in queryset:
            hide_content(thread, by_user=request.user, reason='Hidden via Django admin')
    hide_threads.short_description = 'Hide selected threads'

    def unhide_threads(self, request, queryset):
        from .permissions import unhide_content
        for thread in queryset:
            unhide_content(thread)
    unhide_threads.short_description = 'Unhide selected threads'

    def quarantine_threads(self, request, queryset):
        from .permissions import quarantine_content
        for thread in queryset:
            quarantine_content(thread, by_user=request.user, reason='Quarantined via Django admin')
    quarantine_threads.short_description = 'Quarantine selected threads (invisible to all, incl. author)'

    def restore_threads(self, request, queryset):
        from .permissions import restore_from_quarantine
        for thread in queryset:
            restore_from_quarantine(thread)
    restore_threads.short_description = 'Restore selected threads from quarantine'

    def purge_threads(self, request, queryset):
        # Superuser-only, not just is_staff — purge is irreversible and
        # deserves a higher bar than ordinary Django admin access. The
        # site's Role/can_purge concept governs the API; this is the
        # equivalent floor for the /admin/ route.
        if not request.user.is_superuser:
            self.message_user(request, 'Purging is restricted to superusers.', level='ERROR')
            return
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Permanently deleted {count} thread(s).')
    purge_threads.short_description = 'PERMANENTLY DELETE selected threads (irreversible)'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['short_body', 'thread', 'author', 'poster_ip', 'post_number', 'sage',
                     'is_hidden', 'is_quarantined', 'parent', 'created_at']
    list_filter = ['sage', 'is_hidden', 'is_quarantined']
    search_fields = ['body', 'author__username', 'thread__title']
    readonly_fields = ['post_number', 'created_at', 'hidden_by', 'hidden_at',
                        'quarantined_by', 'quarantined_at', 'poster_ip']
    ordering = ['-created_at']
    actions = ['hide_posts', 'unhide_posts', 'quarantine_posts', 'restore_posts', 'purge_posts']

    def short_body(self, obj):
        return obj.body[:60] + '…' if len(obj.body) > 60 else obj.body
    short_body.short_description = 'Body'

    def hide_posts(self, request, queryset):
        from .permissions import hide_content
        for post in queryset:
            hide_content(post, by_user=request.user, reason='Hidden via Django admin')
    hide_posts.short_description = 'Hide selected posts'

    def unhide_posts(self, request, queryset):
        from .permissions import unhide_content
        for post in queryset:
            unhide_content(post)
    unhide_posts.short_description = 'Unhide selected posts'

    def quarantine_posts(self, request, queryset):
        from .permissions import quarantine_content
        for post in queryset:
            quarantine_content(post, by_user=request.user, reason='Quarantined via Django admin')
    quarantine_posts.short_description = 'Quarantine selected posts (invisible to all, incl. author)'

    def restore_posts(self, request, queryset):
        from .permissions import restore_from_quarantine
        for post in queryset:
            restore_from_quarantine(post)
    restore_posts.short_description = 'Restore selected posts from quarantine'

    def purge_posts(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, 'Purging is restricted to superusers.', level='ERROR')
            return
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Permanently deleted {count} post(s).')
    purge_posts.short_description = 'PERMANENTLY DELETE selected posts (irreversible)'


@admin.register(CommunityInvite)
class CommunityInviteAdmin(admin.ModelAdmin):
    list_display = ['token', 'community', 'created_by', 'created_at', 'expires_at', 'max_uses', 'use_count', 'is_active']
    list_filter = ['is_active', 'community']
    readonly_fields = ['token', 'created_by', 'created_at', 'use_count']
    search_fields = ['community__name', 'created_by__username']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False  # invites are created via the API only


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'emoji', 'thread', 'post', 'created_at']
    list_filter = ['emoji']
    search_fields = ['user__username']
    ordering = ['-created_at']


@admin.register(FeedItem)
class FeedItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'thread', 'post', 'reason', 'created_at']
    list_filter = ['reason']
    search_fields = ['user__username']
    ordering = ['-created_at']


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Moderation queue. CSAM reports are surfaced distinctly — see note below."""
    list_display = ['reason', 'target_link', 'target_author_username', 'reporter', 'status', 'created_at']
    list_filter = ['status', 'reason']
    search_fields = ['details', 'reporter__username', 'target_author_username']
    readonly_fields = [
        'reporter', 'thread', 'post', 'reason', 'details', 'created_at', 'updated_at',
        'target_type', 'target_author', 'target_author_username',
        'target_board_slug', 'target_preview_snapshot', 'target_poster_ip',
    ]
    fields = ['reporter', 'thread', 'post', 'reason', 'details',
              'status', 'resolved_by', 'resolution_note', 'created_at', 'updated_at',
              'target_type', 'target_author', 'target_author_username',
              'target_board_slug', 'target_preview_snapshot', 'target_poster_ip']
    ordering = ['-created_at']
    actions = ['mark_reviewing', 'mark_actioned', 'mark_dismissed']

    def target_link(self, obj):
        target = obj.target
        if target is None:
            # Content is gone (purged) — fall back to the snapshot taken
            # at report-filing time rather than just saying '(deleted)'
            # with no other context. See Report model docstring.
            return obj.target_preview_snapshot or '(deleted, no snapshot — pre-dates this fix)'
        if obj.thread_id:
            url = reverse('admin:core_thread_change', args=[obj.thread.pk])
            label = obj.thread.title[:60]
        else:
            url = reverse('admin:core_post_change', args=[obj.post.pk])
            label = obj.post.body[:60]
        return format_html('<a href="{}">{}</a>', url, label)
    target_link.short_description = 'Reported content'

    def _set_status(self, request, queryset, status):
        queryset.update(status=status, resolved_by=request.user)

    def mark_reviewing(self, request, queryset):
        self._set_status(request, queryset, 'reviewing')
    mark_reviewing.short_description = 'Mark selected as Reviewing'

    def mark_actioned(self, request, queryset):
        self._set_status(request, queryset, 'actioned')
    mark_actioned.short_description = 'Mark selected as Actioned'

    def mark_dismissed(self, request, queryset):
        self._set_status(request, queryset, 'dismissed')
    mark_dismissed.short_description = 'Mark selected as Dismissed'


@admin.register(DisplayNameChangeLog)
class DisplayNameChangeLogAdmin(admin.ModelAdmin):
    """
    Read-only audit trail — entries are only ever created by MyProfileView,
    never edited. Search covers both old and new names so staff can find
    an account by any name it's ever used, which is the whole point of
    this existing (see DisplayNameChangeLog docstring re: Report's purge
    snapshot fields going stale after a rename).
    """
    list_display = ['old_display_name', 'new_display_name', 'user', 'changed_at']
    list_filter = ['changed_at']
    search_fields = ['old_display_name', 'new_display_name', 'user__username']
    readonly_fields = ['user', 'old_display_name', 'new_display_name', 'changed_at']
    ordering = ['-changed_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin — hides the 'Add' button and goes straight to the one
    settings row, creating it with defaults if it doesn't exist yet.
    """

    fieldsets = (
        ('Branding', {
            'fields': ('site_name', 'site_tagline'),
        }),
        ('Boards', {
            'fields': ('max_threads_per_board', 'max_threads_per_user_per_day'),
        }),
        ('Posts & Replies', {
            'fields': ('max_posts_per_thread', 'bump_lock_percent', 'max_post_length', 'max_posts_per_user_per_day'),
        }),
        ('Communities', {
            'fields': ('max_communities', 'max_communities_per_user', 'community_prune_days'),
        }),
        ('Media & Uploads', {
            'fields': (
                'allow_image_uploads', 'max_image_size_mb',
                'allow_avatars', 'max_avatar_size_kb',
                'allow_video_uploads', 'max_video_size_mb', 'max_video_duration_seconds',
            ),
        }),
        ('Registration', {
            'fields': ('registration_open', 'require_email', 'enable_communities', 'allow_markdown', 'allow_post_editing', 'post_edit_window_seconds'),
        }),
        ('Moderation', {
            'fields': (
                'enable_nsfw_boards', 'allow_anonymous_posts',
                'enable_display_name_change_audit', 'display_name_change_cooldown_days',
            ),
        }),
        ('Federation', {
            'description': (
                'ActivityPub federation with other FaceChan instances. Individual '
                'boards also have their own allow_federation flag, checked in '
                'addition to the master switch below.'
            ),
            'fields': (
                'federation_enabled',
                'relay_federation_enabled', 'max_relay_hops',
            ),
        }),
        ('Safety & Compliance', {
            'description': (
                'Jurisdictional safety controls. These ship ON by default — the '
                'safest posture. You are solely responsible for determining and '
                'meeting your own legal obligations. See COMPLIANCE.md. '
                'CSAM detection/reporting is a permanent floor and is not listed here.'
            ),
            'fields': (
                'jurisdiction_mode', 'enable_content_reporting',
                'require_age_confirmation', 'minimum_age',
                'block_nsfw_without_age_gate', 'publish_transparency_info',
                'moderation_contact',
            ),
        }),
    )

    def has_add_permission(self, request):
        """Only one row allowed — hide the Add button if it already exists."""
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion from admin."""
        return False

    def changelist_view(self, request, extra_context=None):
        """Skip the list view and go straight to the settings page."""
        settings_obj = SiteSettings.get()
        return self.change_view(request, str(settings_obj.pk), extra_context=extra_context)


@admin.register(ActivityTier)
class ActivityTierAdmin(admin.ModelAdmin):
    list_display = ('label', 'min_posts', 'order')
    list_editable = ('min_posts', 'order')
    ordering = ('order', 'min_posts')
    list_display_links = ('label',)

@admin.register(WordFilter)
class WordFilterAdmin(admin.ModelAdmin):
    list_display = ['pattern', 'replacement', 'scope', 'board', 'is_regex', 'is_active', 'created_at']
    list_filter = ['scope', 'is_active', 'is_regex', 'board']
    list_editable = ['replacement', 'is_active']
    search_fields = ['pattern', 'replacement']
    ordering = ['scope', 'pattern']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .word_filter import bust_cache
        bust_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        from .word_filter import bust_cache
        bust_cache()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        from .word_filter import bust_cache
        bust_cache()


@admin.register(SitePage)
class SitePageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'published', 'show_in_footer', 'display_order', 'updated_at']
    list_editable = ['published', 'show_in_footer', 'display_order']
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title', 'slug']
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content', 'published', 'show_in_footer', 'display_order'),
        }),
    )
