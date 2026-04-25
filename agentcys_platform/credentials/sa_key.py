"""SA key credential provider — v1.

Retrieves a GCP service account JSON key from Secret Manager, parses it, and
returns it as a dict suitable for ``google.oauth2.service_account.Credentials``.

The Secret Manager URI is stored in ``CustomerCredential.secret_manager_uri``
and has the form::

    projects/{project}/secrets/{secret_id}/versions/{version}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agentcys_platform.credentials.base import CustomerCredentialProvider
from agentcys_platform.security.audit import AuditEvent, PlatformEvent, audit_event_emitter

logger = logging.getLogger(__name__)


class SAKeyCredentialProvider(CustomerCredentialProvider):
    """Retrieves service account JSON keys from Secret Manager."""

    def __init__(self, secret_manager_client: Any) -> None:
        self._client = secret_manager_client

    async def get_credentials(self, credential_id: str, *, secret_uri: str, tenant_id: str = "") -> dict:  # type: ignore[override]
        """Fetch and parse a SA key from Secret Manager.

        *secret_uri* must be the full resource name:
        ``projects/{project}/secrets/{id}/versions/{version}``
        """
        response = self._client.access_secret_version(request={"name": secret_uri})
        raw = response.payload.data.decode("utf-8")
        key_data: dict[str, Any] = json.loads(raw)

        await audit_event_emitter.emit(
            AuditEvent(
                event_type=PlatformEvent.CREDENTIAL_ACCESSED,
                tenant_id=tenant_id,
                resource={"kind": "credential", "id": credential_id},
                details={"sa_email": key_data.get("client_email", "")},
            )
        )

        return key_data
