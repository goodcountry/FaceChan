from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from core import views

router = DefaultRouter()
router.register('boards', views.BoardViewSet, basename='board')
router.register('communities', views.CommunityViewSet, basename='community')
router.register('threads', views.ThreadViewSet, basename='thread')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('federation.urls')),   # AP endpoints + webfinger
    path('api/', include(router.urls)),
    path('api/threads/<uuid:thread_pk>/posts/', views.PostViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('api/threads/<uuid:thread_pk>/posts/<uuid:pk>/', views.PostViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})),
    path('api/threads/<uuid:thread_pk>/posts/<uuid:pk>/react/', views.PostViewSet.as_view({'post': 'react'})),
    path('api/threads/<uuid:thread_pk>/posts/<uuid:pk>/report/', views.PostViewSet.as_view({'post': 'report'})),
    path('api/threads/<uuid:thread_pk>/posts/<uuid:pk>/edit/', views.PostViewSet.as_view({'patch': 'edit'})),
    path('api/site-settings/', views.SiteSettingsView.as_view()),
    path('api/pages/', views.SitePageListView.as_view()),
    path('api/pages/<slug:slug>/', views.SitePageDetailView.as_view()),
    path('api/pages/<slug:slug>/edit/', views.SitePageEditView.as_view()),
    path('api/auth/register/', views.RegisterView.as_view()),
    path('api/auth/login/', views.LoginView.as_view()),
    path('api/feed/', views.FeedView.as_view()),
    path('api/me/', views.MyProfileView.as_view()),  # private profile
    path('api/me/password/', views.PasswordChangeView.as_view()),
    path('api/me/age-confirm/', views.AgeConfirmView.as_view()),
    path('api/me/avatar/', views.AvatarUploadView.as_view()),
    path('api/me/permissions/', views.MyPermissionsView.as_view()),
    path('api/me/watched/', views.WatchedThreadListView.as_view()),
    path('api/me/notifications/unread-count/', views.NotificationUnreadCountView.as_view()),
    path('api/users/<str:username>/', views.PublicProfileView.as_view()),
    path('api/threads/<uuid:pk>/watch/', views.ThreadWatchView.as_view()),
    path('api/threads/<uuid:pk>/mark-seen/', views.ThreadMarkSeenView.as_view()),
    path('api/mod/queue/', views.ModQueueView.as_view()),
    path('api/mod/reports/<uuid:pk>/resolve/', views.ModResolveReportView.as_view()),
    path('api/mod/users/<uuid:user_id>/action/', views.ModUserActionView.as_view()),
    path('api/mod/users/sanctioned/', views.ModSanctionedUsersView.as_view()),
    path('api/mod/quarantine/', views.ModQuarantineQueueView.as_view()),
    path('api/mod/quarantine/<str:content_type>/<uuid:content_id>/action/', views.ModQuarantineActionView.as_view()),
    path('api/invites/<uuid:token>/', views.InvitePreviewView.as_view()),
    path('api/invites/<uuid:token>/join/', views.InviteJoinView.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
