"""
Moderation permission resolver.

Three independent authority scopes exist in FaceChan, and they do not
nest into each other:

1. Site role (User.role) — admin-tier roles are unscoped, reaching every
   board and every community. Every other tier (mod/janitor/board-admin,
   or any custom tier an operator defines) is board-scoped via
   User.board_assignments — it has zero reach outside boards the user
   has actually been assigned to. There is deliberately no "global mod"
   shortcut; "all boards" is just an admin assigning every board.

2. Community membership role (Membership.role) — mod/admin within ONE
   community. Reaches only that community's own threads/posts/members.
   Does NOT extend to the board a community happens to be attached to —
   board moderation is a site-staff concern, not a community-staff one.

3. Ordinary authorship — a user always has a baseline of control over
   their own content regardless of role (e.g. deleting their own post),
   handled separately in views.py, not here. This module is specifically
   about STAFF authority over OTHER people's content.

A piece of content (Thread or Post) can be moderated by:
- a site role whose capability flag covers the action, AND
  (is_admin_tier OR the content's board is in board_assignments)
- OR, if the content belongs to a community, a Membership with
  role in ('mod', 'admin') for that specific community

Whichever grants the broader/relevant permission wins — this module
returns True if EITHER path authorises the action.
"""


def _board_for(content):
    """Thread has .board directly; Post reaches it via .thread.board."""
    if hasattr(content, 'board'):
        return content.board
    return content.thread.board


def _community_for(content):
    if hasattr(content, 'community'):
        return content.community
    return content.thread.community


def _site_role_grants(user, content, capability):
    """Check scope 1: site role, admin-tier unscoped or board-assigned."""
    role = getattr(user, 'role', None)
    if role is None:
        return False
    if not getattr(role, capability, False):
        return False
    if role.is_admin_tier:
        return True
    board = _board_for(content)
    return user.board_assignments.filter(pk=board.pk).exists()


def _community_role_grants(content, user):
    """
    Check scope 2: community mod/admin. Community moderation doesn't have
    the same granular capability-flag system as site roles — being a
    community mod or admin grants full moderation authority within that
    community, mirroring how Membership.role already works elsewhere in
    the codebase (see CommunityViewSet) rather than introducing a second,
    differently-shaped permission model for the same membership table.
    """
    community = _community_for(content)
    if community is None:
        return False
    from .models import Membership
    return Membership.objects.filter(
        user=user, community=community, role__in=('mod', 'admin')
    ).exists()


def _community_creator_grants(content, user):
    """Check if user is the creator of the community this content belongs to."""
    community = _community_for(content)
    if community is None:
        return False
    return community.created_by_id == user.pk


def can_moderate(user, content, capability):
    """
    Main entry point. `capability` is one of the Role boolean field names:
    'can_hide', 'can_resolve_reports', 'can_quarantine', 'can_lock_threads',
    'can_pin_threads', 'can_suspend', 'can_ban', 'can_manage_roles'.

    `content` is a Thread or Post instance.

    NOTE: 'can_purge' is deliberately NOT checked here — see
    can_purge_content() below, which hard-requires admin-tier in code
    regardless of the flag, since purging is irreversible and shouldn't
    be delegable by data alone.

    can_suspend/can_ban/can_manage_roles are site-staff-only concepts —
    community membership never grants them, regardless of capability name
    matching, since community mods moderate community content, not user
    accounts or site role assignments. Only scope 1 is checked for those.

    can_pin_threads is also granted to the community creator and community
    admins for threads within their own community.
    """
    if not user or not user.is_authenticated:
        return False

    if capability in ('can_suspend', 'can_ban', 'can_manage_roles'):
        return _site_role_grants(user, content, capability)

    if _site_role_grants(user, content, capability):
        return True

    # Community moderation only meaningfully maps to the "ordinary content
    # moderation" capabilities — a community mod hiding or quarantining a
    # thread in their own community is the expected case here. Purge is
    # excluded entirely (see can_purge_content) — community mods never
    # get an irreversible action regardless of capability flags.
    if capability in ('can_hide', 'can_resolve_reports', 'can_quarantine', 'can_lock_threads'):
        return _community_role_grants(content, user)

    # Pinning: community admins and the community creator can pin within
    # their own community.
    if capability == 'can_pin_threads':
        if _community_role_grants(content, user):
            return True
        return _community_creator_grants(content, user)

    return False


def can_access_private_thread(user, thread):
    """
    Gate for private-message threads (Thread.is_private_message=True).

    This is deliberately separate from can_moderate()'s board/community
    scoping above — a private thread lives on a hidden system board, and
    the normal "board-assigned staff can act on this board's content" path
    must NOT apply to it (an admin assigning a mod to every board must not
    incidentally hand them everyone's DMs). Access is either:
      - participant, or
      - SiteSettings.private_message_staff_access_enabled is True AND the
        user holds an admin-tier role — the narrow, audited, operator-only
        override for things like a law-enforcement request. Board-scoped
        staff (mod/janitor/board-admin) never qualify, regardless of flags.

    Returns True unconditionally for non-private threads, so callers can
    use this as a blanket check without branching on is_private_message
    themselves.
    """
    if not thread.is_private_message:
        return True
    if not user or not user.is_authenticated:
        return False
    if thread.participants.filter(pk=user.pk).exists():
        return True
    from .models import SiteSettings
    settings = SiteSettings.get()
    if settings.private_message_staff_access_enabled:
        role = getattr(user, 'role', None)
        if role is not None and role.is_admin_tier:
            return True
    return False


def can_purge_content(user):
    """
    Purge is irreversible, so it's hard-gated to admin-tier in code, not
    just by the can_purge flag — a board-admin or mod role should never
    be able to purge no matter how Role rows get edited. This is the one
    capability check in this module that ISN'T also satisfiable via
    community membership; purging isn't a community-moderation concept.
    """
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, 'role', None)
    return bool(role and role.is_admin_tier and role.can_purge)


def hide_content(content, *, by_user, reason=''):
    """Mark a Thread or Post hidden, recording who and why."""
    from django.utils import timezone
    content.is_hidden = True
    content.hidden_by = by_user
    content.hidden_at = timezone.now()
    content.hidden_reason = reason[:200]
    content.save(update_fields=['is_hidden', 'hidden_by', 'hidden_at', 'hidden_reason'])


def unhide_content(content):
    """Reverse hide_content — clears the audit fields too, since they
    described the (now-reversed) hide action, not a permanent record."""
    content.is_hidden = False
    content.hidden_by = None
    content.hidden_at = None
    content.hidden_reason = ''
    content.save(update_fields=['is_hidden', 'hidden_by', 'hidden_at', 'hidden_reason'])


def quarantine_content(content, *, by_user, reason=''):
    """
    Tier 2: invisible to EVERYONE including its own author, pending an
    admin decision to restore or purge. Stays in the database — this is
    explicitly NOT deletion. See COMPLIANCE.md for the legal caveat: this
    function exists so a single non-admin moderation action can't destroy
    content that might need to be preserved (e.g. for law enforcement, or
    because deleting it might itself carry jurisdiction-specific legal
    weight that hasn't been assessed) — it does not on its own resolve
    what an operator's actual retention/handling obligations are.
    """
    from django.utils import timezone
    content.is_quarantined = True
    content.quarantined_by = by_user
    content.quarantined_at = timezone.now()
    content.quarantine_reason = reason[:200]
    content.save(update_fields=[
        'is_quarantined', 'quarantined_by', 'quarantined_at', 'quarantine_reason'
    ])


def restore_from_quarantine(content):
    """Admin-only at the call site (views.py) — reverses quarantine_content."""
    content.is_quarantined = False
    content.quarantined_by = None
    content.quarantined_at = None
    content.quarantine_reason = ''
    content.save(update_fields=[
        'is_quarantined', 'quarantined_by', 'quarantined_at', 'quarantine_reason'
    ])


def purge_content(content):
    """
    Tier 3: actually deletes the row. Irreversible. Callers MUST check
    can_purge_content(user) before calling this — this function itself
    does not check permissions, since by the time something is being
    purged the caller should already have verified admin-tier authority;
    this is a thin wrapper purely so the action is named consistently
    with hide/quarantine rather than a bare .delete() scattered in views.
    """
    content.delete()


def pin_thread(thread):
    """Pin a thread and disable comments (default behaviour for stickies)."""
    thread.is_pinned = True
    thread.comments_disabled = True
    thread.save(update_fields=['is_pinned', 'comments_disabled'])


def unpin_thread(thread):
    """Unpin a thread and re-enable comments."""
    thread.is_pinned = False
    thread.comments_disabled = False
    thread.save(update_fields=['is_pinned', 'comments_disabled'])


def set_comments_disabled(thread, *, disabled):
    """Toggle comments on/off independently of pin state."""
    thread.comments_disabled = disabled
    thread.save(update_fields=['comments_disabled'])


def can_manage_pages(user):
    """True if the user has the can_manage_pages role flag or is a superuser."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = getattr(user, 'role', None)
    if role is None:
        try:
            from .models import Role
            role = Role.objects.get(users=user)
        except Exception:
            return False
    return bool(getattr(role, 'can_manage_pages', False))
