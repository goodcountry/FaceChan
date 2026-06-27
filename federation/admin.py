"""
federation/admin.py

Django admin for the federation layer.
The RemoteInstance admin is the operator's primary tool for approving
or blocking remote instances.
"""

from django.contrib import admin
from federation.models import Actor, RemoteInstance, RemoteActor, Follow, FederationActivity, RemoteBoardMapping, RemoteBoard


@admin.register(RemoteInstance)
class RemoteInstanceAdmin(admin.ModelAdmin):
    list_display = ['domain', 'status', 'created_at', 'updated_at']
    list_filter = ['status']
    search_fields = ['domain', 'notes']
    list_editable = ['status']
    ordering = ['domain']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('domain', 'status', 'actor_url', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'actor_type', 'created_at']
    list_filter = ['actor_type']
    readonly_fields = ['id', 'public_key_pem', 'created_at']
    # Private key deliberately excluded from admin display
    exclude = ['private_key_pem']


@admin.register(RemoteActor)
class RemoteActorAdmin(admin.ModelAdmin):
    list_display = ['username', 'instance', 'actor_type', 'fetched_at']
    list_filter = ['actor_type', 'instance']
    search_fields = ['username', 'ap_id']
    readonly_fields = ['ap_id', 'fetched_at', 'raw_json']


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['remote_actor', 'local_actor', 'accepted', 'created_at']
    list_filter = ['accepted']
    readonly_fields = ['id', 'created_at']


@admin.register(FederationActivity)
class FederationActivityAdmin(admin.ModelAdmin):
    list_display = ['activity_type', 'direction', 'status', 'remote_instance', 'created_at']
    list_filter = ['direction', 'activity_type', 'status']
    search_fields = ['activity_id', 'error']
    readonly_fields = ['id', 'payload', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(RemoteBoardMapping)
class RemoteBoardMappingAdmin(admin.ModelAdmin):
    list_display = ['instance', 'remote_slug', 'local_board', 'created_at']
    list_filter = ['instance', 'local_board']
    search_fields = ['remote_slug', 'instance__domain', 'local_board__slug']
    ordering = ['instance__domain', 'remote_slug']
    readonly_fields = ['id', 'created_at']
    fieldsets = (
        (None, {
            'fields': ('instance', 'remote_slug', 'local_board'),
            'description': (
                'Map a board on a remote instance to a local board. '
                'Threads from the remote board will be filed under the local board. '
                'Only approved instances are eligible.'
            ),
        }),
        ('Meta', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(RemoteBoard)
class RemoteBoardAdmin(admin.ModelAdmin):
    list_display = ['remote_slug', 'name', 'instance', 'nsfw', 'fetched_at']
    list_filter = ['instance', 'nsfw']
    search_fields = ['remote_slug', 'name', 'instance__domain']
    readonly_fields = ['id', 'actor_url', 'inbox_url', 'fetched_at']
    ordering = ['instance__domain', 'remote_slug']
