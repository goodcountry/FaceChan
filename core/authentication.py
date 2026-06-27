"""
Custom DRF authentication wrapping TokenAuthentication.

DRF's TokenAuthentication has no concept of token expiry or revocation
beyond deleting the row — a token issued before a ban/suspension stays
valid afterwards unless something checks. This makes a ban/suspension
take effect immediately on the next authenticated request, not just at
the next login.
"""
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class SanctionAwareTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if user.is_banned:
            raise AuthenticationFailed('This account has been permanently banned.')
        if user.is_suspended:
            raise AuthenticationFailed(
                f'This account is suspended until {user.suspended_until.isoformat()}.'
            )
        return user, token
