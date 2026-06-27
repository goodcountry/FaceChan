"""
federation/models.py

ActivityPub federation layer for FaceChan.

Architecture overview:
  - Actor: represents a Board or User as an ActivityPub identity with a keypair
  - RemoteInstance: the allowlist of trusted remote FaceChan instances
  - RemoteActor: cached representation of an Actor on a remote instance
  - Follow: tracks which remote instances follow which local boards
  - FederationActivity: audit log of all inbound/outbound activities
"""

import uuid
from django.db import models
from django.conf import settings
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


class Actor(models.Model):
    """
    Local ActivityPub Actor — one per Board (Group) or per User (Person).

    Each Actor owns an RSA keypair. The private key signs outgoing HTTP
    requests. The public key is published at the Actor's AP endpoint so
    remote servers can verify our signatures.

    We store board and user as nullable FKs — exactly one will be set.
    """
    ACTOR_TYPES = [
        ('Group', 'Group'),    # Board
        ('Person', 'Person'),  # User
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_type = models.CharField(max_length=10, choices=ACTOR_TYPES)

    # Exactly one of these is set
    board = models.OneToOneField(
        'core.Board', null=True, blank=True,
        on_delete=models.CASCADE, related_name='ap_actor'
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name='ap_actor'
    )

    # RSA keypair — private key is PEM, never exposed via API
    private_key_pem = models.TextField(editable=False)
    public_key_pem = models.TextField(editable=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Exactly one of board/user must be set — enforced in clean()
            # (DB constraint would need a check constraint; we enforce in save)
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.board and self.user:
            raise ValidationError('Actor cannot be linked to both a Board and a User.')
        if not self.board and not self.user:
            raise ValidationError('Actor must be linked to either a Board or a User.')

    def save(self, *args, **kwargs):
        if not self.private_key_pem:
            self._generate_keypair()
        super().save(*args, **kwargs)

    def _generate_keypair(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        self.public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    @property
    def ap_id(self):
        """Canonical ActivityPub URL for this Actor."""
        from federation.utils import actor_url
        return actor_url(self)

    @property
    def key_id(self):
        return f'{self.ap_id}#main-key'

    def __str__(self):
        if self.board:
            return f'Group:/{self.board.slug}/'
        if self.user:
            return f'Person:{self.user.username}'
        return f'Actor:{self.pk}'


class RemoteInstance(models.Model):
    """
    Allowlist of remote FaceChan instances permitted to federate with us.

    Incoming activities from instances not on this list are rejected.
    Operators must explicitly approve instances — open federation is not
    the default (compliance risk).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('blocked', 'Blocked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=253, unique=True)  # e.g. 'other.facechan.example'
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    # Their instance actor URL (fetched during handshake)
    actor_url = models.URLField(blank=True)

    # Human notes for the operator — why approved/blocked
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['domain']

    def __str__(self):
        return f'{self.domain} ({self.status})'

    @property
    def is_approved(self):
        return self.status == 'approved'


class RemoteActor(models.Model):
    """
    Cached representation of an Actor on a remote instance.

    We fetch and cache remote Actor JSON when we first see a Follow or
    activity from them. The public key is stored so we can verify their
    HTTP Signatures without a round-trip on every request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(
        RemoteInstance, on_delete=models.CASCADE, related_name='actors'
    )
    ap_id = models.URLField(unique=True)          # Their canonical Actor URL
    actor_type = models.CharField(max_length=20)   # Group, Person, Service, etc.
    username = models.CharField(max_length=200, blank=True)
    display_name = models.CharField(max_length=200, blank=True)
    inbox_url = models.URLField()
    public_key_pem = models.TextField()
    key_id = models.URLField()                     # Their key URL (for sig verification)

    # Raw JSON snapshot — useful for debugging and future fields
    raw_json = models.JSONField(default=dict)

    fetched_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.username}@{self.instance.domain}'


class Follow(models.Model):
    """
    A remote Actor (typically a remote board Group) following one of our
    local boards.

    When we publish a new thread, we deliver a Create(Note) activity to
    the inbox of every approved follower's instance.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    local_actor = models.ForeignKey(
        Actor, on_delete=models.CASCADE, related_name='followers'
    )
    remote_actor = models.ForeignKey(
        RemoteActor, on_delete=models.CASCADE, related_name='following'
    )

    # The AP activity ID of the Follow request — needed to send Accept
    follow_activity_id = models.URLField()

    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('local_actor', 'remote_actor')]

    def __str__(self):
        return f'{self.remote_actor} → {self.local_actor}'


class FederationActivity(models.Model):
    """
    Audit log of all inbound and outbound ActivityPub activities.

    Kept for debugging and compliance. Inbound activities that fail
    validation are logged here with error details.
    """
    DIRECTION_CHOICES = [
        ('in', 'Inbound'),
        ('out', 'Outbound'),
    ]
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    activity_type = models.CharField(max_length=50)   # Create, Follow, Accept, Undo…
    activity_id = models.URLField(blank=True)          # AP @id of the activity
    local_actor = models.ForeignKey(
        Actor, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='activities'
    )
    remote_instance = models.ForeignKey(
        RemoteInstance, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='activities'
    )
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='queued')
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.direction}:{self.activity_type} [{self.status}]'


class RemoteBoardMapping(models.Model):
    """
    Operator-configured mapping from a remote board to a local board.

    When a Create(Note) activity arrives from a remote instance, we look up
    the remote board slug here to determine which local board to file it under.
    If no mapping exists the activity is discarded — operators opt in per-board.

    Example:
        instance=other.tld, remote_slug=Pols → local_board=/politics/
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(
        RemoteInstance, on_delete=models.CASCADE, related_name='board_mappings'
    )
    remote_slug = models.CharField(
        max_length=200,
        help_text='Board slug on the remote instance e.g. "Pols" or "TechyStuff"'
    )
    local_board = models.ForeignKey(
        'core.Board', on_delete=models.CASCADE, related_name='remote_mappings'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Outbound follow state:
    #   None  → no Follow sent yet
    #   False → Follow delivered, waiting for Accept
    #   True  → Accept received, follow is live
    follow_accepted = models.BooleanField(
        null=True, default=None,
        help_text='None=not sent, False=pending Accept, True=accepted'
    )

    class Meta:
        unique_together = [('instance', 'remote_slug')]
        ordering = ['instance__domain', 'remote_slug']

    def __str__(self):
        return f'{self.instance.domain}/{self.remote_slug} → /{self.local_board.slug}/'


class RemoteBoard(models.Model):
    """
    Cached board list fetched from a remote FaceChan instance's /ap/instance
    endpoint. Populated automatically when an instance is approved.

    Used to populate the RemoteBoardMapping admin dropdown so operators
    don't have to type remote slugs manually.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(
        RemoteInstance, on_delete=models.CASCADE, related_name='remote_boards'
    )
    remote_slug = models.CharField(max_length=200)
    name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    nsfw = models.BooleanField(default=False)
    actor_url = models.URLField(blank=True)
    inbox_url = models.URLField(blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('instance', 'remote_slug')]
        ordering = ['instance__domain', 'remote_slug']

    def __str__(self):
        return f'{self.instance.domain}/{self.remote_slug}'
