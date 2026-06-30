from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
import uuid


class Role(models.Model):
    """
    Site-wide staff role. Capability flags are data, not code, so the site
    owner can define exactly what each tier can do via Django admin without
    a code change — e.g. splitting "Junior Janitor" off from "Janitor" with
    a narrower flag set.

    Scope model (see User.board_assignments below for the mechanism):
    - Admin-tier roles (is_admin_tier=True) are unscoped — they reach every
      board and every community regardless of what's in board_assignments.
      Only an admin-tier role can manage Role objects and assign other
      users to roles, including other admins.
    - Every other tier (janitor/mod/board-admin, or any custom tier an
      operator adds) is board-scoped: it only has authority on the boards
      a user holding that role has been explicitly assigned to via
      User.board_assignments. "All boards" is just an admin assigning
      every board — there's no separate unscoped mechanism for these
      tiers, by design, so trust is built up board-by-board rather than
      granted globally by default.
    - This is independent of, and does not extend to, per-community
      Membership.role (community mod/admin) — that authority stays scoped
      to its own community and never reaches the underlying board.
    """
    name = models.CharField(max_length=50, unique=True)
    tier = models.PositiveSmallIntegerField(
        default=0,
        help_text='Higher = more capable. Used for ordering/display only — '
                   'actual power comes from the capability flags below.'
    )
    is_admin_tier = models.BooleanField(
        default=False,
        help_text='Unscoped (every board/community) and can manage roles & '
                   'role/board assignments. There should usually be very few '
                   'roles with this set.'
    )
    can_hide = models.BooleanField(default=False, help_text='Hide threads/posts (reversible, visible to author/staff).')
    can_resolve_reports = models.BooleanField(default=False, help_text='Mark reports reviewing/actioned/dismissed.')
    can_quarantine = models.BooleanField(
        default=False,
        help_text='Remove content from ALL visibility, including its own author — stays in the '
                   'database pending an admin decision to restore or purge. Reversible. Intended '
                   'for board-admin tier and above: content that may be illegal in some '
                   'jurisdictions, or that law enforcement might need, gets held rather than '
                   'destroyed by a single non-admin action. See COMPLIANCE.md for the legal '
                   'caveat on retention — this is architecture, not legal advice.'
    )
    can_purge = models.BooleanField(
        default=False,
        help_text='Permanently delete quarantined content. IRREVERSIBLE. Enforced as admin-tier-only '
                   'in code regardless of this flag — see permissions.py can_purge_content(). The flag '
                   'still exists for visibility/audit in the admin, not because a non-admin role can '
                   'ever actually be granted it.'
    )
    can_lock_threads = models.BooleanField(default=False)
    can_pin_threads = models.BooleanField(default=False, help_text='Pin/unpin threads and toggle comments disabled on any thread within scope.')
    can_suspend = models.BooleanField(default=False, help_text='Issue timed suspensions.')
    can_ban = models.BooleanField(default=False, help_text='Issue permanent bans.')
    can_manage_roles = models.BooleanField(
        default=False,
        help_text='Assign/change other users\' roles and board assignments. '
                   'Should normally only be set alongside is_admin_tier.'
    )
    can_manage_pages = models.BooleanField(
        default=False,
        help_text='Create, edit, and publish site pages (Rules, FAQ, etc.).'
    )

    class Meta:
        ordering = ['-tier']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Semi-anonymous: username required, real name never stored."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    avatar_pdq_hash = models.CharField(
        max_length=64, null=True, blank=True, editable=False,
        help_text='perceptual hash (pHash) of the avatar image. Used for CSAM hash-matching. '
                  'Null until an avatar is uploaded or if hashing failed.'
    )
    bio = models.TextField(max_length=500, blank=True)
    tagline = models.CharField(max_length=100, blank=True)
    display_badge = models.CharField(max_length=20, blank=True)  # 'founder', 'mod', 'premium', etc.
    post_count = models.PositiveIntegerField(default=0)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Staff role — null means an ordinary member with no site-staff capability.
    role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.SET_NULL, related_name='users'
    )
    # Which boards this user's role applies to. Irrelevant for admin-tier
    # roles (those are unscoped regardless of this field's contents) —
    # meaningful for every other tier. "All boards" = an admin populating
    # this with every Board, not a separate flag.
    board_assignments = models.ManyToManyField(
        'Board', blank=True, related_name='staff_assignments'
    )

    # Sanctions — independent of role. A banned/suspended user keeps their
    # account and role (if any) but cannot authenticate while the sanction
    # is active.
    is_banned = models.BooleanField(default=False)
    suspended_until = models.DateTimeField(null=True, blank=True)

    # Display name — shown on threads, posts, and profile.
    # Defaults to username at registration. Can be changed by the user
    # (subject to cooldown). Duplicates are allowed — multiple users can
    # display as "anonymous" or any other name. The login username is
    # always stable and private.
    display_name = models.CharField(max_length=150, blank=True)

    # Set whenever the display name actually changes (see MyProfileView).
    # Null means "never changed" — a new account isn't subject to cooldown
    # before its first display name change.
    display_name_last_changed_at = models.DateTimeField(null=True, blank=True)

    # Federation: stub accounts created to represent remote ActivityPub actors.
    # These accounts cannot log in — they exist only as an author FK target
    # so remote threads have a proper author record.
    is_remote = models.BooleanField(default=False)
    remote_actor_url = models.URLField(
        null=True, blank=True, unique=True,
        help_text='AP Actor URL for remote stub users. Null for local accounts.'
    )

    # Media posting grant — operator-only toggle.
    # When site-wide image/video uploads are disabled, users with this flag
    # set can still attach media. Has no effect when uploads are globally on
    # (everyone can post media in that case anyway).
    can_post_media = models.BooleanField(
        default=False,
        help_text='Allow this user to attach images and videos even when site-wide '
                  'media uploads are disabled. Set by an operator; has no effect '
                  'when uploads are globally enabled.'
    )

    # Age confirmation for NSFW board visibility — persisted per-account so it
    # carries across devices/browsers once a user logs in. Logged-out visitors
    # have no account to attach this to, so they continue to use the
    # client-side (X-Age-Verified header) flow on every fresh session — this
    # field has no effect for them. Settable by the user themselves on first
    # confirmation, or by an operator directly in admin.
    age_verified = models.BooleanField(
        default=False,
        help_text='Whether this user has confirmed they meet the minimum age '
                  'requirement to view NSFW boards. Persists across devices once '
                  'set. Has no effect on logged-out/anonymous visitors.'
    )

    REQUIRED_FIELDS = []

    def __str__(self):
        return self.username

    @property
    def is_suspended(self):
        return bool(self.suspended_until and self.suspended_until > timezone.now())

    @property
    def is_sanctioned(self):
        """True if currently blocked from authenticating, for any reason."""
        return self.is_banned or self.is_suspended


class Board(models.Model):
    """4chan-style board e.g. /tech/, /cooking/"""
    slug = models.SlugField(unique=True, max_length=20)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, default='📋')
    nsfw = models.BooleanField(default=False)
    allow_images = models.BooleanField(default=True, help_text='Allow users to attach images to threads and posts on this board.')
    allow_videos = models.BooleanField(default=True, help_text='Allow users to attach short video clips (MP4/WebM) to threads and posts on this board. Automatically disabled when allow_images is off.')
    allow_video_sound = models.BooleanField(default=True, help_text='Allow video clips to include an audio track. Automatically disabled when allow_videos is off.')
    allow_links = models.BooleanField(
        default=False,
        help_text='Allow users to post hyperlinks (http:// or https://) in thread titles, '
                  'thread bodies, and replies on this board. '
                  'Has no effect when the global "allow links" setting is disabled.'
    )
    allow_federation = models.BooleanField(
        default=True,
        help_text='Include this board in ActivityPub federation. '
                  'Disable to keep the board local-only — it will not appear in the '
                  'instance board list and threads will not be delivered to remote instances. '
                  'Admin-only setting.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """
        Enforce media dependency rules:
          - No images → no videos, no sound (videos require images to be enabled)
          - No videos → no sound

        Turning images back on does NOT auto-enable video or sound — the
        admin must opt back in explicitly. This is enforced here at the model
        layer so it applies regardless of how the data enters (admin, shell,
        migrations, API).
        """
        if not self.allow_images:
            if self.allow_videos:
                raise ValidationError(
                    'Video uploads require image uploads to be enabled. '
                    'Disable images first, or enable images to allow video.'
                )
            if self.allow_video_sound:
                raise ValidationError(
                    'Video sound requires image uploads to be enabled.'
                )
        if not self.allow_videos and self.allow_video_sound:
            raise ValidationError(
                'Video sound requires video uploads to be enabled.'
            )

    def save(self, *args, **kwargs):
        """
        Silently enforce cascade-off on save (without raising ValidationError).
        clean() is called by Django admin and form validation — this handles
        direct saves (e.g. from shell or seed command) where clean() may not
        be called.
        """
        if not self.allow_images:
            self.allow_videos = False
            self.allow_video_sound = False
        if not self.allow_videos:
            self.allow_video_sound = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f'/{self.slug}/'


class Community(models.Model):
    """Facebook-style group / community."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    banner = models.ImageField(upload_to='banners/', null=True, blank=True)
    board = models.ForeignKey(Board, null=True, blank=True, on_delete=models.SET_NULL, related_name='communities')
    members = models.ManyToManyField(User, through='Membership', related_name='communities')
    is_private = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_communities')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    ROLE_CHOICES = [('member', 'Member'), ('mod', 'Moderator'), ('admin', 'Admin')]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'community')


class CommunityInvite(models.Model):
    """
    A tokenised invite link for a private (or public) community.
    Admin/mods generate links; anyone with the link can join.

    Expiry is checked at join time — expired or exhausted links
    are rejected but kept in the DB so admins can see history.
    Revocation is via is_active=False.
    """
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='invites')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invites_created')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Leave blank for a non-expiring link.'
    )
    max_uses = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Leave blank for unlimited uses.'
    )
    use_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text='Deactivate to revoke the link.')

    def is_valid(self):
        """False if revoked, expired, or exhausted."""
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_uses is not None and self.use_count >= self.max_uses:
            return False
        return True

    def __str__(self):
        return f'Invite to {self.community} ({self.token})'


class Thread(models.Model):
    """OP thread — lives on a Board, optionally in a Community."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='threads')
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.SET_NULL, related_name='threads')
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='threads')
    title = models.CharField(max_length=300)
    body = models.TextField()
    image = models.ImageField(upload_to='thread_images/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='thread_thumbs/', null=True, blank=True)
    image_pdq_hash = models.CharField(
        max_length=64, null=True, blank=True, editable=False,
        help_text='perceptual hash (pHash) of the thread image. Used for CSAM hash-matching. '
                  'Null if no image attached or if hashing failed.'
    )
    video = models.FileField(upload_to='thread_videos/', null=True, blank=True)
    video_thumbnail = models.ImageField(upload_to='thread_video_thumbs/', null=True, blank=True)
    video_pdq_hash = models.CharField(
        max_length=64, null=True, blank=True, editable=False,
        help_text='perceptual hash (pHash) of the video first frame. Used for CSAM hash-matching. '
                  'Null if no video attached or if hashing failed.'
    )
    video_duration = models.FloatField(
        null=True, blank=True,
        help_text='Duration of the attached video in seconds.'
    )
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    comments_disabled = models.BooleanField(
        default=False,
        help_text='Disable new comments on this thread. Set automatically when pinned; '
                  'can also be toggled independently to cool down any thread.'
    )
    reply_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    last_reply_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    poster_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text='IP address of the poster at submission time. Admin-only. Raw address — handle as personal data per your jurisdiction.'
    )

    # Federation: set when this thread arrived via ActivityPub from a remote instance.
    # is_remote=True threads are read-only — local users can reply but the OP
    # is owned by the remote instance. remote_ap_id is the canonical AP URL of
    # the Note on the origin server; used to deduplicate inbound deliveries.
    is_remote = models.BooleanField(default=False)
    remote_ap_id = models.URLField(
        null=True, blank=True, unique=True,
        help_text='ActivityPub Note ID on the origin server. Null for local threads.'
    )
    remote_actor_url = models.URLField(
        null=True, blank=True,
        help_text='AP Actor URL of the remote author. Null for local threads. '
                  'Preserved as-is through relay hops — always the ORIGINAL author, '
                  'never a relaying instance\'s stub user.'
    )

    # Relay federation (optional, off by default — see SiteSettings.
    # relay_federation_enabled). When a thread is relayed onward through a
    # chain of instances rather than only delivered origin-to-follower
    # directly, these track how it travelled so loops can be prevented and
    # forwarded copies can carry their full path for debugging.
    relay_hop_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of instance-to-instance hops this activity has travelled. '
                  '0 for content that originated here or arrived direct from its '
                  'origin. Incremented by 1 each time an instance relays it onward. '
                  'Relaying stops once SiteSettings.max_relay_hops is reached.'
    )
    relay_seen_instances = models.JSONField(
        default=list, blank=True,
        help_text='List of instance domains this activity has already passed through '
                  '(origin first, most recent relay last). Used to prevent relay loops — '
                  'an instance must never relay an activity back to a domain already in '
                  'this list. Empty for content that originated here.'
    )

    # Moderation: hidden, not deleted. Hidden content stays in the DB and
    # remains visible to its author and to staff with reach over it — it's
    # just excluded from public listings/retrieval. See core/permissions.py
    # for who is allowed to set/clear this.
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=200, blank=True)

    # Moderation tier 2: quarantine. Stronger than hide — invisible to
    # EVERYONE including its own author, pending an admin decision to
    # restore or purge. Board-admin tier and above. See COMPLIANCE.md:
    # content that might be illegal in some jurisdiction, or that law
    # enforcement might need, is held here rather than destroyed by a
    # single non-admin action — this is architecture for that judgement
    # call, not a substitute for getting actual legal advice on retention.
    is_quarantined = models.BooleanField(default=False)
    quarantined_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    quarantined_at = models.DateTimeField(null=True, blank=True)
    quarantine_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-is_pinned', '-last_reply_at']

    def __str__(self):
        return self.title


class Post(models.Model):
    """
    A reply within a Thread.
    parent=None  → top-level comment
    parent=Post  → reply to a comment (one level deep)
    sage=True    → reply does not bump the thread
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='posts')
    body = models.TextField()
    image = models.ImageField(upload_to='post_images/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='post_thumbs/', null=True, blank=True)
    image_pdq_hash = models.CharField(
        max_length=64, null=True, blank=True, editable=False,
        help_text='perceptual hash (pHash) of the post image. Used for CSAM hash-matching. '
                  'Null if no image attached or if hashing failed.'
    )
    video = models.FileField(upload_to='post_videos/', null=True, blank=True)
    video_thumbnail = models.ImageField(upload_to='post_video_thumbs/', null=True, blank=True)
    video_pdq_hash = models.CharField(
        max_length=64, null=True, blank=True, editable=False,
        help_text='perceptual hash (pHash) of the video first frame. Used for CSAM hash-matching. '
                  'Null if no video attached or if hashing failed.'
    )
    video_duration = models.FloatField(
        null=True, blank=True,
        help_text='Duration of the attached video in seconds.'
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    sage = models.BooleanField(default=False)  # True = don't bump thread
    post_number = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    edit_count = models.PositiveIntegerField(default=0)
    poster_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text='IP address of the poster at submission time. Admin-only. Raw address — handle as personal data per your jurisdiction.'
    )

    # Moderation: hidden, not deleted — same model as Thread above.
    is_hidden = models.BooleanField(default=False)
    hidden_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=200, blank=True)

    # Moderation tier 2: quarantine — same model as Thread above.
    is_quarantined = models.BooleanField(default=False)
    quarantined_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    quarantined_at = models.DateTimeField(null=True, blank=True)
    quarantine_reason = models.CharField(max_length=200, blank=True)

    # Federation: remote replies arrive from other FaceChan instances via AP.
    # is_remote=True → this post was authored on a remote instance.
    # remote_ap_id   → canonical AP URL of the Note on the origin server (dedup key).
    # remote_actor_url → AP URL of the remote Person who wrote it.
    is_remote = models.BooleanField(default=False)
    remote_ap_id = models.URLField(
        null=True, blank=True, unique=True,
        help_text='Canonical ActivityPub URL of this post on its origin server. '
                  'Null for local posts. Used for deduplication on inbound delivery.'
    )
    remote_actor_url = models.URLField(
        null=True, blank=True,
        help_text='AP URL of the remote actor who authored this post. '
                  'Null for local posts. Preserved as-is through relay hops — '
                  'always the ORIGINAL author, never a relaying instance\'s stub user.'
    )

    # Relay federation — see matching fields on Thread for full explanation.
    relay_hop_count = models.PositiveIntegerField(default=0)
    relay_seen_instances = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Post by {self.author} in {self.thread}'

    @property
    def is_top_level(self):
        return self.parent_id is None


class Reaction(models.Model):
    EMOJI_CHOICES = [
        ('👍', 'Like'), ('❤️', 'Love'), ('😂', 'Haha'),
        ('😮', 'Wow'), ('😢', 'Sad'), ('😡', 'Angry'), ('🔥', 'Fire'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=5, choices=EMOJI_CHOICES)
    thread = models.ForeignKey(Thread, null=True, blank=True, on_delete=models.CASCADE, related_name='reactions')
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name='reactions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'thread'), ('user', 'post')]


class SiteSettings(models.Model):
    """
    Singleton model — only one row should ever exist.
    Accessible in admin at /admin/core/sitesettings/1/change/
    Use SiteSettings.get() anywhere in code to read current settings.
    """

    # ── Branding ──────────────────────────────────────────────────────────────
    site_name = models.CharField(
        max_length=100, default='FaceChan',
        help_text='Displayed in the header and browser tab.')
    site_tagline = models.CharField(
        max_length=200, blank=True, default='Anonymous-first community platform',
        help_text='Short tagline shown beneath the site name.')

    # ── Boards ────────────────────────────────────────────────────────────────
    max_threads_per_board = models.PositiveIntegerField(
        default=200,
        help_text='Once reached, the oldest non-pinned thread is pruned when a new one is posted.')
    max_threads_per_user_per_day = models.PositiveIntegerField(
        default=10,
        help_text='Rate limit — threads a single user can create per rolling 24 hours '
                  '(not a calendar-day reset; the window slides with the clock). 0 = unlimited.')

    # ── Posts / replies ───────────────────────────────────────────────────────
    max_posts_per_thread = models.PositiveIntegerField(
        default=500,
        help_text='Thread locks automatically when this many replies are reached.')
    bump_lock_percent = models.PositiveIntegerField(
        default=75,
        validators=[MaxValueValidator(95)],
        help_text='Thread stops bumping to the top once reply count reaches this percentage '
                  'of max_posts_per_thread. E.g. 75 means a 500-post thread bump-locks at '
                  '375 replies. Set to 0 to disable bump locking (threads bump until locked). '
                  'Maximum 95 — values above this are clamped in code.'
    )
    max_post_length = models.PositiveIntegerField(
        default=5000,
        help_text='Maximum character length for a post body.')
    max_posts_per_user_per_day = models.PositiveIntegerField(
        default=100,
        help_text='Rate limit — posts a single user can make per rolling 24 hours '
                  '(not a calendar-day reset; the window slides with the clock). 0 = unlimited.')

    # ── Communities ───────────────────────────────────────────────────────────
    max_communities = models.PositiveIntegerField(
        default=100,
        help_text='Maximum number of communities allowed on this instance.')
    max_communities_per_user = models.PositiveIntegerField(
        default=5,
        help_text='Maximum number of communities a single user can create.')
    community_prune_days = models.PositiveIntegerField(
        default=30,
        help_text='Automatically delete communities (and all their threads and posts) '
                  'that have had no new posts for this many days. '
                  'No exceptions — all communities are subject to this rule. '
                  '0 = pruning disabled.'
    )

    # ── Media / uploads ───────────────────────────────────────────────────────
    allow_image_uploads = models.BooleanField(
        default=True,
        help_text='Allow users to attach images to threads and posts.')
    max_image_size_mb = models.PositiveIntegerField(
        default=8,
        help_text='Maximum image upload size in megabytes.')
    allow_avatars = models.BooleanField(
        default=False,
        help_text='Allow users to upload profile avatars. Disabled by default — '
                  'enable only if you are comfortable hosting user-uploaded images.')
    max_avatar_size_kb = models.PositiveIntegerField(
        default=512,
        help_text='Maximum avatar upload size in kilobytes. 512KB is plenty for a profile picture.')
    allow_video_uploads = models.BooleanField(
        default=True,
        help_text='Allow users to attach short video clips (MP4/WebM) to threads and posts. '
                  'Requires FFmpeg to be installed on the server.')
    max_video_size_mb = models.PositiveIntegerField(
        default=50,
        help_text='Maximum video upload size in megabytes.')
    max_video_duration_seconds = models.PositiveIntegerField(
        default=300,
        help_text='Maximum video duration in seconds (default 300 = 5 minutes). '
                  '0 = no duration limit (not recommended).')

    # ── Registration ──────────────────────────────────────────────────────────
    registration_open = models.BooleanField(
        default=True,
        help_text='Allow new user registrations. Disable to make the instance invite-only.')
    require_email = models.BooleanField(
        default=False,
        help_text='Require an email address at registration.')
    enable_communities = models.BooleanField(
        default=True,
        help_text='Enable the communities feature. When off, community creation is disabled '
                  'and the communities nav link is hidden. Existing communities are unaffected.')
    allow_markdown = models.BooleanField(
        default=True,
        help_text='Allow markdown formatting in posts and replies. When off, body text is rendered as plain text.')
    allow_links = models.BooleanField(
        default=False,
        help_text='Master switch for hyperlinks. When off, no board may allow hyperlinks regardless of its own setting. '
                  'When on, individual boards can enable or disable links independently. '
                  'Links means http:// or https:// URLs — bare domain names are always allowed.'
    )
    allow_post_editing = models.BooleanField(
        default=False,
        help_text='Allow users to edit their own posts after submission.')
    post_edit_window_seconds = models.PositiveIntegerField(
        default=90,
        help_text='How long (in seconds) a user has to edit a post after submission. 0 = unlimited.'
    )

    # ── Moderation ────────────────────────────────────────────────────────────
    enable_nsfw_boards = models.BooleanField(
        default=True,
        help_text='Allow boards to be marked NSFW.')
    allow_anonymous_posts = models.BooleanField(
        default=False,
        help_text='Allow posting without being logged in (future feature).')
    enable_display_name_change_audit = models.BooleanField(
        default=True,
        help_text='Log every display name change (old name, new name, when) to '
                  'DisplayNameChangeLog. Independent of the cooldown below — '
                  'turning this off stops new log entries but does not affect '
                  'whether changes are still rate-limited.')
    display_name_change_cooldown_days = models.PositiveIntegerField(
        default=14,
        help_text='Minimum days a user must wait between display name changes. '
                  '0 = no cooldown. Enforced via User.display_name_last_changed_at, '
                  'which is tracked regardless of the audit-log toggle above.')

    # ── Federation ────────────────────────────────────────────────────────────
    federation_enabled = models.BooleanField(
        default=True,
        help_text='Master switch for ActivityPub federation. '
                  'Disable to pause all inbound and outbound federation without '
                  'removing instance mappings or board configurations. '
                  'Individual boards can also be excluded via their allow_federation flag.'
    )
    relay_federation_enabled = models.BooleanField(
        default=False,
        help_text='When on, threads/replies received from one federated instance are '
                  're-forwarded to this instance\'s own followers, preserving the '
                  'original author and Note id — building a relay chain (1→2→3) rather '
                  'than requiring every instance to follow every other instance directly. '
                  'Off by default: the safer, simpler mode where each instance only '
                  'delivers what it originates itself. Has no effect if '
                  'federation_enabled is off.'
    )
    max_relay_hops = models.PositiveIntegerField(
        default=5,
        help_text='Maximum number of instance-to-instance hops a relayed activity may '
                  'travel before this instance stops forwarding it further. Caps relay '
                  'chain length even if the seen-instances loop guard is somehow '
                  'bypassed (e.g. a non-FaceChan AP server in the chain that doesn\'t '
                  'preserve the seen-instances field). Only relevant when '
                  'relay_federation_enabled is on.'
    )

    # ── Safety & Compliance (jurisdictional) ──────────────────────────────────
    # These settings let an operator configure the instance for their own legal
    # jurisdiction. They ship ON by default (safest posture). Operators are
    # solely responsible for determining and meeting their own legal obligations.
    # See COMPLIANCE.md. Note: CSAM detection/reporting is a permanent,
    # non-configurable floor and is NOT controlled here.
    JURISDICTION_CHOICES = [
        ('uk', 'United Kingdom (Online Safety Act)'),
        ('eu', 'European Union (Digital Services Act)'),
        ('us', 'United States (Section 230 host)'),
        ('other', 'Other / operator-defined'),
    ]
    jurisdiction_mode = models.CharField(
        max_length=10, choices=JURISDICTION_CHOICES, default='uk',
        help_text='Operator\'s legal jurisdiction. Informational — sets sensible '
                  'defaults and is surfaced in transparency reporting.')
    enable_content_reporting = models.BooleanField(
        default=True,
        help_text='Show a "report" control on threads and posts that routes to '
                  'the moderation queue. Strongly recommended in all jurisdictions; '
                  'required-in-effect under the UK OSA and EU DSA.')
    require_age_confirmation = models.BooleanField(
        default=True,
        help_text='Require users to confirm they meet the minimum age at registration. '
                  'A jurisdictional control — UK/EU operators will generally need this; '
                  'operators elsewhere may not.')
    minimum_age = models.PositiveIntegerField(
        default=18,
        help_text='Minimum age (years) a user must confirm at registration when '
                  'age confirmation is enabled.')
    block_nsfw_without_age_gate = models.BooleanField(
        default=True,
        help_text='Hide NSFW boards behind the age gate. Disable only where your '
                  'jurisdiction does not require age-gating of adult content.')
    publish_transparency_info = models.BooleanField(
        default=True,
        help_text='Expose a public transparency page (instance jurisdiction, '
                  'moderation contact, reporting routes). Good-faith disclosure.')
    moderation_contact = models.EmailField(
        blank=True,
        help_text='Public contact address for legal / moderation enquiries and '
                  'content reports. Recommended for OSA/DSA operators.')

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'{self.site_name} — Site Settings'

    @classmethod
    def get(cls):
        """Always returns the singleton row, creating it with defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        """Force pk=1 so there can only ever be one row."""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion — reset to defaults instead."""
        pass


class Report(models.Model):
    """
    A user report against a Thread or a Post — exactly one of the two is set.
    Feeds the moderation queue. Gated on SiteSettings.enable_content_reporting
    at the API layer; the model itself has no opinion on that toggle.
    """
    REASON_CHOICES = [
        ('spam', 'Spam or advertising'),
        ('harassment', 'Harassment or bullying'),
        ('illegal', 'Illegal content'),
        ('csam', 'Child sexual abuse material'),
        ('violence', 'Violence or graphic content'),
        ('hate', 'Hate speech'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('reviewing', 'Reviewing'),
        ('actioned', 'Actioned'),
        ('dismissed', 'Dismissed'),
    ]
    TARGET_TYPE_CHOICES = [
        ('thread', 'Thread'),
        ('post', 'Post'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='reports_filed')
    # SET_NULL, not CASCADE: purging the underlying content (see
    # core/permissions.py purge_content) must not destroy the Report row
    # along with it — the resolution record (who purged it, when, why)
    # is exactly the audit trail this whole feature exists to keep, and
    # losing it the moment the content is gone would defeat that purpose.
    # target/get_target_preview already handle thread=None/post=None.
    thread = models.ForeignKey(
        Thread, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports')
    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports')

    # ── Snapshot fields ──────────────────────────────────────────────
    # Everything below is captured ONCE, at report-creation time (see
    # _create_report in views.py), specifically so it survives the
    # underlying content being purged. Before these existed, the queue
    # derived target_type/author/board/preview live from self.target —
    # which is exactly what purge_content() sets to None, silently
    # erasing "who was reported" right when the audit trail matters
    # most. These are deliberately NOT kept in sync if the content is
    # later edited or the user renamed — they're a record of what was
    # reported, not a live mirror of current state.
    # Nullable at the DB level purely so existing rows didn't need an
    # invented value at migration time (see migration 0014) — every new
    # Report is always created with this set by _create_report in
    # views.py. Treat it as required in practice, just not DB-enforced.
    target_type = models.CharField(max_length=10, choices=TARGET_TYPE_CHOICES, null=True, blank=True)
    target_author = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports_against')
    # Kept even if target_author's User row is later deleted outright
    # (SET_NULL only clears the FK, not this) — and useful as a quick
    # display value without a join. Recognising repeat-reported users by
    # username, even across an account deletion, is part of the point.
    target_author_username = models.CharField(max_length=150, blank=True)
    target_board_slug = models.CharField(max_length=100, blank=True)
    target_preview_snapshot = models.CharField(max_length=200, blank=True)
    target_poster_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text='IP of the content author at the time the report was filed. Snapshotted so it survives content purge.'
    )

    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    details = models.TextField(
        max_length=1000, blank=True,
        help_text='Optional extra context from the reporter.')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    resolved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports_resolved')
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                # Exactly one of thread/post set (the normal case), OR
                # both null — which happens when the reported content has
                # been purged (see Report.thread/post SET_NULL above) and
                # the Report row survives as a standing record of what was
                # done. What's never valid is BOTH set at once.
                condition=(
                    Q(thread__isnull=False, post__isnull=True) |
                    Q(thread__isnull=True, post__isnull=False) |
                    Q(thread__isnull=True, post__isnull=True)
                ),
                name='report_at_most_one_target',
            ),
        ]

    def __str__(self):
        target = self.thread or self.post
        target_desc = target if target else '(content purged)'
        return f'Report ({self.get_reason_display()}) on {target_desc} — {self.status}'

    @property
    def target(self):
        return self.thread or self.post


class DisplayNameChangeLog(models.Model):
    """
    One row per display name change, written by MyProfileView whenever a user
    changes their own display name — only if SiteSettings.enable_display_name_change_audit
    is on. The cooldown itself (User.display_name_last_changed_at) is tracked
    unconditionally and doesn't depend on this table being populated.

    Exists because content audit trails record a display name at a point in
    time — if that user later renames, staff have no way to know the two are
    the same account without this log.
    """
    user = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='display_name_changes')
    old_display_name = models.CharField(max_length=150)
    new_display_name = models.CharField(max_length=150)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.old_display_name} → {self.new_display_name} ({self.changed_at:%Y-%m-%d})'


class FeedItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feed')
    thread = models.ForeignKey(Thread, null=True, blank=True, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE)
    reason = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class WatchedThread(models.Model):
    """
    A user watching a thread — they receive a FeedItem (reason='thread_reply')
    whenever someone else posts in it.

    last_seen_reply_count: the reply_count at the time the user last visited
    the thread. Used to compute unread count = thread.reply_count - last_seen.
    Also drives the notification bell's badge count.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watched_threads')
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='watchers')
    last_seen_reply_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'thread')
        ordering = ['-created_at']

    @property
    def unread_count(self):
        return max(0, self.thread.reply_count - self.last_seen_reply_count)

    def __str__(self):
        return f'{self.user.username} watching {self.thread_id}'


class ActivityTier(models.Model):
    """
    Operator-defined user activity tiers based on post count.

    The public profile shows the highest tier a user has reached
    (highest min_posts <= user.post_count) rather than the raw count,
    keeping stalking ability minimal while still rewarding prolific posters.

    Tiers are fully configurable — operators can add, remove, rename, and
    reorder them freely via Django admin. If no tiers are defined, the
    public profile falls back to "Member".

    Default tiers (created by the seed command):
        Lurker (0+), Regular (10+), Veteran (100+),
        Prolific Poster (500+), Legend (2000+)
    """
    label = models.CharField(max_length=50, help_text='Displayed on the public profile.')
    min_posts = models.PositiveIntegerField(
        help_text='Minimum post count to reach this tier.'
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text='Display order in admin. Lower numbers appear first. '
                  'Does not affect tier calculation — that always uses min_posts.'
    )

    class Meta:
        ordering = ['order', 'min_posts']

    def __str__(self):
        return f'{self.label} ({self.min_posts}+ posts)'

    @classmethod
    def for_user(cls, post_count):
        """
        Return the label of the highest tier the user has reached,
        or 'Member' if no tiers are configured.
        """
        tier = cls.objects.filter(min_posts__lte=post_count).order_by('-min_posts').first()
        return tier.label if tier else 'Member'


class WordFilter(models.Model):
    """
    Duck Roll — word/phrase substitution applied at read time, never on write.

    Raw text is always stored in the DB unchanged. Substitution happens
    in serializers so filters can be updated or removed and old content
    immediately reflects the change. Staff always see raw text in Django admin.

    Scope:
    - 'site'  — applied on every board
    - 'board' — applied only on the specified board (board FK must be set)

    If is_regex is True, pattern is compiled as a case-insensitive Python regex.
    If False, it's a plain case-insensitive substring match.
    """
    SCOPE_CHOICES = [
        ('site', 'Site-wide'),
        ('board', 'Board-specific'),
    ]

    pattern = models.CharField(
        max_length=500,
        help_text='Word, phrase, or regex pattern to match (case-insensitive).'
    )
    replacement = models.CharField(
        max_length=500,
        default='quack',
        help_text='Text to substitute in place of the matched pattern.'
    )
    scope = models.CharField(
        max_length=10, choices=SCOPE_CHOICES, default='site',
        help_text='Site-wide applies everywhere. Board-specific applies only to the selected board.'
    )
    board = models.ForeignKey(
        'Board', null=True, blank=True, on_delete=models.CASCADE,
        related_name='word_filters',
        help_text='Required when scope is "board". Ignored for site-wide filters.'
    )
    is_regex = models.BooleanField(
        default=False,
        help_text='Treat pattern as a Python regex. If off, plain substring match.'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scope', 'pattern']

    def __str__(self):
        scope_label = f'/{self.board.slug}/' if self.board else 'site-wide'
        return f'"{self.pattern}" → "{self.replacement}" ({scope_label})'


class SitePage(models.Model):
    """
    Operator-authored pages — Rules, FAQ, About, Privacy Policy, etc.
    Content is markdown; rendered by MarkdownBody on the frontend.
    """
    slug = models.SlugField(
        unique=True,
        help_text='URL-safe identifier, e.g. "rules", "faq", "about". '
                  'Accessible at /pages/<slug>/.'
    )
    title = models.CharField(max_length=200)
    content = models.TextField(
        blank=True,
        help_text='Markdown content. Leave blank to show a placeholder.'
    )
    published = models.BooleanField(
        default=True,
        help_text='Unpublished pages are not accessible to the public.'
    )
    show_in_footer = models.BooleanField(
        default=True,
        help_text='Show a link to this page in the site footer.'
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text='Lower numbers appear first in the footer. 0 = unordered.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'title']

    def __str__(self):
        return f'{self.title} (/{self.slug}/)'
