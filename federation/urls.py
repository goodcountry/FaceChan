"""
federation/urls.py

All ActivityPub-facing URLs live here.
Mounted at the root in facechan/urls.py.
"""

from django.urls import path
from federation import views

urlpatterns = [
    # Instance info — public board discovery for federation setup
    path('ap/instance', views.InstanceInfoView.as_view(), name='ap-instance'),

    # Actor discovery
    path('.well-known/webfinger', views.WebfingerView.as_view(), name='webfinger'),

    # Board (Group) Actor endpoints
    path('ap/boards/<slug:slug>', views.BoardActorView.as_view(), name='ap-board-actor'),
    path('ap/boards/<slug:slug>/inbox', views.BoardInboxView.as_view(), name='ap-board-inbox'),
    path('ap/boards/<slug:slug>/outbox', views.BoardOutboxView.as_view(), name='ap-board-outbox'),
    path('ap/boards/<slug:slug>/followers', views.BoardFollowersView.as_view(), name='ap-board-followers'),

    # User (Person) Actor endpoint
    path('ap/users/<str:username>', views.UserActorView.as_view(), name='ap-user-actor'),
]

# ── Federation management API (admin only) ─────────────────────────────────
from federation import api_views

api_urlpatterns = [
    path('api/federation/status/', api_views.FederationStatusView.as_view(), name='federation-status'),
    path('api/federation/instances/', api_views.RemoteInstanceListView.as_view(), name='federation-instances'),
    path('api/federation/instances/<uuid:pk>/', api_views.RemoteInstanceDetailView.as_view(), name='federation-instance-detail'),
    path('api/federation/instances/<uuid:pk>/refresh/', api_views.RefreshInstanceBoardsView.as_view(), name='federation-instance-refresh'),
    path('api/federation/instances/<uuid:pk>/boards/', api_views.RemoteBoardListView.as_view(), name='federation-instance-boards'),
    path('api/federation/mappings/', api_views.RemoteBoardMappingListView.as_view(), name='federation-mappings'),
    path('api/federation/mappings/<uuid:pk>/', api_views.RemoteBoardMappingDetailView.as_view(), name='federation-mapping-detail'),
    path('api/federation/local-boards/', api_views.LocalBoardListView.as_view(), name='federation-local-boards'),
]

urlpatterns = urlpatterns + api_urlpatterns
