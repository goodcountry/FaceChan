"""
core/captcha.py

Bot protection for FaceChan.

Two layers, applied in order:

1. Honeypot — a hidden `website` field in every submission form. Legitimate
   users never fill it in; bots typically do. Silently returns HTTP 200 on
   failure so the bot doesn't know it was caught.

2. mCaptcha (optional) — self-hosted proof-of-work captcha. Only active when
   MCAPTCHA_URL and MCAPTCHA_SITE_KEY are set in the environment. The frontend
   loads the mCaptcha widget; the backend verifies the token here before
   accepting the submission.

Neither layer uses third-party services (no Google, no Cloudflare). Both are
Tor-compatible.
"""

import logging
import httpx
from django.conf import settings
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def mcaptcha_configured():
    """True if mCaptcha env vars are both present and non-empty."""
    return bool(
        getattr(settings, 'MCAPTCHA_URL', None) and
        getattr(settings, 'MCAPTCHA_SITE_KEY', None)
    )


def check_honeypot(request_data):
    """
    Returns a silent-200 Response if the honeypot field is filled, else None.
    The field is named `website` — present in the form but hidden off-screen.
    Bots fill it; humans don't.
    """
    if request_data.get('website'):
        logger.info('Honeypot triggered — silent reject')
        return Response({}, status=200)
    return None


def check_mcaptcha(request_data):
    """
    Verifies the mCaptcha token against the operator's mCaptcha instance.
    Returns a 400 Response on failure, None on success (or if not configured).
    """
    if not mcaptcha_configured():
        return None

    token = request_data.get('mcaptcha_token', '')
    if not token:
        return Response({'error': 'Please complete the captcha.'}, status=400)

    try:
        resp = httpx.post(
            f"{settings.MCAPTCHA_URL.rstrip('/')}/api/v1/pow/siteverify",
            json={
                'token': token,
                'key': settings.MCAPTCHA_SITE_KEY,
            },
            timeout=10,
        )
        data = resp.json()
        if not data.get('valid'):
            logger.warning('mCaptcha verification failed: %s', data)
            return Response({'error': 'Captcha verification failed. Please try again.'}, status=400)
    except Exception as e:
        logger.error('mCaptcha verification error: %s', e)
        return Response({'error': 'Captcha service unavailable. Please try again.'}, status=503)

    return None


def run_bot_checks(request_data):
    """
    Run all bot checks in order. Returns a Response to send immediately if
    any check fails, or None if all pass.

    Usage in a view:
        bot_check = run_bot_checks(request.data)
        if bot_check:
            return bot_check
    """
    check = check_honeypot(request_data)
    if check:
        return check
    check = check_mcaptcha(request_data)
    if check:
        return check
    return None
