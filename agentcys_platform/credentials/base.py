"""Credential provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CustomerCredentialProvider(ABC):
    """Abstract base class for customer GCP credential providers.

    v1 implements SA key retrieval from Secret Manager (sa_key.py).
    v2 will add Workload Identity Federation support.
    """

    @abstractmethod
    async def get_credentials(self, credential_id: str) -> dict:
        """Return GCP credentials for the given credential_id.

        Implementors must record credential access in the audit log.
        """
        ...
