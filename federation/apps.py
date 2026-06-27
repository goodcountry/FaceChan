from django.apps import AppConfig


class FederationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'federation'

    def ready(self):
        import federation.signals  # noqa
        self._check_federation_base_url()

    def _check_federation_base_url(self):
        """
        Warn at startup if FEDERATION_BASE_URL is not configured.

        If it's still the default (localhost) federation is effectively
        disabled — remote servers cannot reach us and we cannot identify
        ourselves to them. This is expected on first boot of a Tor instance
        before the onion address is known. Log a clear warning so operators
        know what to do next.
        """
        import logging
        from django.conf import settings

        logger = logging.getLogger('federation')
        base_url = getattr(settings, 'FEDERATION_BASE_URL', '')

        if not base_url or base_url == 'http://localhost:8000':
            logger.warning(
                '\n'
                '╔══════════════════════════════════════════════════════════════╗\n'
                '║  FEDERATION_BASE_URL is not configured                       ║\n'
                '║                                                              ║\n'
                '║  Federation is running but this instance has no public       ║\n'
                '║  address. Remote servers cannot discover or contact you.     ║\n'
                '║                                                              ║\n'
                '║  If this is a Tor instance:                                  ║\n'
                '║    1. Check your .onion address:                             ║\n'
                '║       docker compose -f docker-compose.prod.yml              ║\n'
                '║                      -p facechan-prod logs tor               ║\n'
                '║    2. Add to .env:                                           ║\n'
                '║       FEDERATION_BASE_URL=http://youraddress.onion           ║\n'
                '║    3. Restart: docker compose -f docker-compose.prod.yml     ║\n'
                '║                -p facechan-prod up -d                        ║\n'
                '║                                                              ║\n'
                '║  If this is a clearnet instance:                             ║\n'
                '║       FEDERATION_BASE_URL=https://yourdomain.tld             ║\n'
                '║                                                              ║\n'
                '║  Federation will work normally once this is set.             ║\n'
                '║  This instance operates fine without it — federation         ║\n'
                '║  is simply disabled until configured.                        ║\n'
                '╚══════════════════════════════════════════════════════════════╝'
            )
        elif not base_url.startswith('https://') and not base_url.startswith('http://'):
            logger.warning(
                'FEDERATION_BASE_URL looks malformed (no scheme): %s\n'
                'Expected format: https://yourdomain.tld or http://youraddress.onion',
                base_url
            )
