"""HMAC-SHA256 signing and verification for service-to-service auth.

Used between the API (signer) and the Worker (verifier) to ensure that
Cloud Tasks payloads originate from the platform API and have not been
tampered with in transit.

Header contract on every Cloud Tasks delivery:
    X-Agentcys-Signature  — hex-encoded HMAC-SHA256(secret, timestamp.body)
    X-Agentcys-Timestamp  — Unix epoch seconds (str) of when the payload was signed

Usage::

    # API side — sign before enqueuing
    sig, ts = sign_payload(body_bytes, settings.HMAC_SIGNING_SECRET)
    headers["X-Agentcys-Signature"] = sig
    headers["X-Agentcys-Timestamp"] = ts

    # Worker side — verify on receipt
    if not verify_signature(body_bytes, sig, ts, settings.HMAC_SIGNING_SECRET):
        raise HTTPException(401, "invalid_signature")
"""

from __future__ import annotations

import hashlib
import hmac
import time

# Maximum acceptable clock skew between signer and verifier.
MAX_TIMESTAMP_DRIFT_SECONDS = 300  # 5 minutes


def sign_payload(payload_bytes: bytes, secret: str) -> tuple[str, str]:
    """Create an HMAC-SHA256 signature for *payload_bytes*.

    Returns ``(signature_hex, timestamp_str)``.

    The signed message is ``"{timestamp}.{payload_bytes}"`` so the timestamp
    is cryptographically bound to the payload and cannot be replayed with a
    different body.
    """
    timestamp = str(int(time.time()))
    signed_content = f"{timestamp}.".encode() + payload_bytes
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_content,
        hashlib.sha256,
    ).hexdigest()
    return signature, timestamp


def verify_signature(
    payload_bytes: bytes,
    signature_hex: str,
    timestamp_str: str,
    secret: str,
    *,
    max_drift: int = MAX_TIMESTAMP_DRIFT_SECONDS,
) -> bool:
    """Verify an inbound HMAC-SHA256 signature with replay protection.

    Returns ``True`` only when:
    1. The timestamp is within *max_drift* seconds of the current time.
    2. The HMAC matches the value computed from *secret* and *payload_bytes*.

    Uses ``hmac.compare_digest`` to prevent timing side-channel attacks.
    """
    try:
        ts = int(timestamp_str)
    except (ValueError, TypeError):
        return False

    if abs(time.time() - ts) > max_drift:
        return False

    signed_content = f"{timestamp_str}.".encode() + payload_bytes
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_content,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_hex)
