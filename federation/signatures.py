"""
federation/signatures.py

HTTP Signatures for ActivityPub.

ActivityPub uses HTTP Signatures (draft-cavage-http-signatures) to
authenticate requests between servers. Every outgoing POST to a remote
inbox is signed with the sending Actor's RSA private key. Every incoming
POST to our inbox is verified against the sender's published public key.

Spec: https://datatracker.ietf.org/doc/html/draft-cavage-http-signatures
"""

import base64
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


# ---------------------------------------------------------------------------
# Signing outgoing requests
# ---------------------------------------------------------------------------

def sign_request(method, url, body_bytes, actor):
    """
    Build the headers dict needed to sign an outgoing ActivityPub request.

    Returns a dict of headers to merge into the outgoing request:
        Date, Digest, Signature

    Args:
        method:     HTTP method string, e.g. 'POST'
        url:        Full target URL string
        body_bytes: Request body as bytes
        actor:      Local Actor model instance (owns the private key)
    """
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path
    if parsed.query:
        path = f'{path}?{parsed.query}'

    date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')

    # Digest: SHA-256 of body, base64-encoded
    digest = base64.b64encode(
        hashlib.sha256(body_bytes).digest()
    ).decode()
    digest_header = f'SHA-256={digest}'

    # Build the signing string
    signed_headers = '(request-target) host date digest'
    signing_string = (
        f'(request-target): {method.lower()} {path}\n'
        f'host: {host}\n'
        f'date: {date}\n'
        f'digest: {digest_header}'
    )

    # Load private key and sign
    private_key = serialization.load_pem_private_key(
        actor.private_key_pem.encode(), password=None
    )
    signature_bytes = private_key.sign(
        signing_string.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    signature_b64 = base64.b64encode(signature_bytes).decode()

    signature_header = (
        f'keyId="{actor.key_id}",'
        f'algorithm="rsa-sha256",'
        f'headers="{signed_headers}",'
        f'signature="{signature_b64}"'
    )

    return {
        'Date': date,
        'Digest': digest_header,
        'Signature': signature_header,
        'Host': host,
    }


# ---------------------------------------------------------------------------
# Verifying incoming requests
# ---------------------------------------------------------------------------

def verify_request(method, path, headers, body_bytes, public_key_pem):
    """
    Verify the HTTP Signature on an incoming request.

    Returns True if valid, raises VerificationError if not.

    Args:
        method:         HTTP method string
        path:           Request path (with query string if present)
        headers:        Dict-like of request headers (case-insensitive access needed)
        body_bytes:     Raw request body bytes
        public_key_pem: Sender's public key PEM string (fetched from their Actor)
    """
    sig_header = _get_header(headers, 'Signature')
    if not sig_header:
        raise VerificationError('Missing Signature header')

    sig_parts = _parse_signature_header(sig_header)
    signed_header_names = sig_parts.get('headers', 'date').split()
    signature_b64 = sig_parts.get('signature', '')

    # Verify digest if present
    digest_header = _get_header(headers, 'Digest')
    if digest_header:
        _verify_digest(body_bytes, digest_header)

    # Reconstruct signing string
    signing_parts = []
    for header_name in signed_header_names:
        if header_name == '(request-target)':
            signing_parts.append(f'(request-target): {method.lower()} {path}')
        else:
            value = _get_header(headers, header_name)
            if value is None:
                raise VerificationError(f'Signed header missing: {header_name}')
            signing_parts.append(f'{header_name}: {value}')
    signing_string = '\n'.join(signing_parts)

    # Verify signature
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    signature = base64.b64decode(signature_b64)
    try:
        public_key.verify(
            signature,
            signing_string.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        raise VerificationError('HTTP Signature verification failed')

    return True


def _verify_digest(body_bytes, digest_header):
    """Check the Digest header matches the actual body."""
    if digest_header.startswith('SHA-256='):
        expected = digest_header[len('SHA-256='):]
        actual = base64.b64encode(hashlib.sha256(body_bytes).digest()).decode()
        if actual != expected:
            raise VerificationError('Digest mismatch — body has been tampered with')
    # Unknown digest algorithms: skip (be lenient on receive)


def _parse_signature_header(header):
    """Parse Signature: keyId="...",algorithm="...",headers="...",signature="..." """
    parts = {}
    for match in re.finditer(r'(\w+)="([^"]*)"', header):
        parts[match.group(1)] = match.group(2)
    return parts


def _get_header(headers, name):
    """Case-insensitive header lookup."""
    name_lower = name.lower()
    for key, value in headers.items():
        if key.lower() == name_lower:
            return value
    return None


class VerificationError(Exception):
    """Raised when an HTTP Signature cannot be verified."""
    pass
