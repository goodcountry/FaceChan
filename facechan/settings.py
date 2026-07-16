from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

INSTALLED_APPS = [
    'daphne',                          # must be first — replaces runserver with ASGI
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_celery_beat',
    'channels',
    'core',
    'federation',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'facechan.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [],
               'APP_DIRS': True, 'OPTIONS': {'context_processors': [
                   'django.template.context_processors.debug',
                   'django.template.context_processors.request',
                   'django.contrib.auth.context_processors.auth',
                   'django.contrib.messages.context_processors.messages']}}]

WSGI_APPLICATION = 'facechan.wsgi.application'

# Database — SQLite for dev, PostgreSQL for prod
DATABASE_URL = config('DATABASE_URL', default=None)
if DATABASE_URL:
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

AUTH_USER_MODEL = 'core.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['core.authentication.SanctionAwareTokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG  # tighten in production
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv()) if not DEBUG else []

# CSRF — tell Django which origins are trusted when behind a reverse proxy.
# Add your domain here when deploying to clearnet e.g. https://facechan.example.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost,http://localhost:8080', cast=Csv())

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

USE_TZ = True
TIME_ZONE = 'UTC'

# ── Security headers ──────────────────────────────────────────────────────────
# Blocks reflected XSS attempts in older browsers that support the X-XSS-Protection header.
SECURE_BROWSER_XSS_FILTER = True
# Prevents this site being embedded in an iframe on another domain (clickjacking).
X_FRAME_OPTIONS = 'DENY'
# Prevents browsers from MIME-sniffing a response away from its declared content-type.
# Stops a malicious upload being executed as a script if the content-type header is wrong.
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ── Channels / WebSockets ──────────────────────────────────────────────────────
ASGI_APPLICATION = 'facechan.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        # RedisPubSubChannelLayer uses Redis pub/sub rather than the
        # list-based blocking pop (BRPOP) used by the default
        # RedisChannelLayer. The blocking-pop path in channels_redis 4.x +
        # redis-py 5.x raises spurious "Timeout reading from redis" on idle
        # connections, which crashes consumers (WS close 1011) and causes
        # endless client reconnects. Pub/sub has no such idle-read timeout.
        'BACKEND': 'channels_redis.pubsub.RedisPubSubChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://redis:6379/1')],
        },
    },
}

# R2 — uncomment when ready
# R2_ACCOUNT_ID = config('R2_ACCOUNT_ID', default='')
# R2_ACCESS_KEY = config('R2_ACCESS_KEY', default='')
# R2_SECRET_KEY = config('R2_SECRET_KEY', default='')
# R2_BUCKET = config('R2_BUCKET', default='facechan-media')
# R2_PUBLIC_URL = config('R2_PUBLIC_URL', default='')

# ── ActivityPub / Federation ───────────────────────────────────────────────────
# Canonical public URL of this instance — no trailing slash.
# Set in .env: FEDERATION_BASE_URL=https://facechan.example
FEDERATION_BASE_URL = config("FEDERATION_BASE_URL", default="http://localhost:8000")

# Tor SOCKS proxy for OUTBOUND connections to .onion instances. Clearnet
# destinations ignore this and connect directly. The socks5h:// scheme makes
# Tor resolve DNS (required for .onion). Empty string disables onion outbound
# (onion deliveries/fetches will fail loudly rather than hang).
# Set in .env: FEDERATION_SOCKS_PROXY=socks5h://tor-proxy:9150 (peterdavehello/tor-socks-proxy default port)
FEDERATION_SOCKS_PROXY = config("FEDERATION_SOCKS_PROXY", default="socks5h://tor-proxy:9150")

# ── mCaptcha (optional) ───────────────────────────────────────────────────────
# Self-hosted proof-of-work captcha. Set both vars to enable.
# Leave unset (or empty) to disable — honeypot protection still applies.
# https://mcaptcha.org/
MCAPTCHA_URL = config("MCAPTCHA_URL", default="")
MCAPTCHA_SITE_KEY = config("MCAPTCHA_SITE_KEY", default="")

