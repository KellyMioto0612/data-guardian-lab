"""Secretless Microsoft Entra credential selection for Azure integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class AzureAuthMode(StrEnum):
    """Supported token sources; none use a password or client secret."""

    AUTO = "auto"
    AZURE_CLI = "azure_cli"
    MANAGED_IDENTITY = "managed_identity"
    WORKLOAD_IDENTITY = "workload_identity"


class AzureAuthenticationError(RuntimeError):
    """Raised when a secretless Azure authentication mode is invalid or unavailable."""


@dataclass(frozen=True)
class AzureAuthSettings:
    """Non-secret settings required to acquire Microsoft Entra tokens."""

    mode: AzureAuthMode = AzureAuthMode.AUTO
    client_id: str = ""
    tenant_id: str = ""
    federated_token_file: str = ""

    @classmethod
    def from_environment(cls) -> AzureAuthSettings:
        raw_mode = os.getenv("AZURE_AUTH_MODE", AzureAuthMode.AUTO).strip().lower()
        try:
            mode = AzureAuthMode(raw_mode)
        except ValueError as error:
            allowed = ", ".join(item.value for item in AzureAuthMode)
            raise AzureAuthenticationError(f"AZURE_AUTH_MODE must be one of: {allowed}") from error
        return cls(
            mode=mode,
            client_id=os.getenv("AZURE_CLIENT_ID", "").strip(),
            tenant_id=os.getenv("AZURE_TENANT_ID", "").strip(),
            federated_token_file=os.getenv("AZURE_FEDERATED_TOKEN_FILE", "").strip(),
        )


class AzureCredentialFactory:
    """Create an explicit credential without falling back to secret-based credentials."""

    def __init__(self, settings: AzureAuthSettings | None = None) -> None:
        self.settings = settings or AzureAuthSettings.from_environment()

    def create(self) -> Any:
        """Create the configured credential without contacting Azure."""
        identity = self._load_identity()
        mode = self._resolved_mode()
        if mode is AzureAuthMode.AZURE_CLI:
            return identity.AzureCliCredential()
        if mode is AzureAuthMode.MANAGED_IDENTITY:
            kwargs = {"client_id": self.settings.client_id} if self.settings.client_id else {}
            return identity.ManagedIdentityCredential(**kwargs)
        if mode is AzureAuthMode.WORKLOAD_IDENTITY:
            self._validate_workload_identity()
            return identity.WorkloadIdentityCredential(
                tenant_id=self.settings.tenant_id,
                client_id=self.settings.client_id,
                token_file_path=self.settings.federated_token_file,
            )
        raise AzureAuthenticationError(f"Unsupported Azure authentication mode: {mode}")

    def _resolved_mode(self) -> AzureAuthMode:
        if self.settings.mode is not AzureAuthMode.AUTO:
            return self.settings.mode
        if self.settings.federated_token_file:
            return AzureAuthMode.WORKLOAD_IDENTITY
        azure_identity_markers = ("IDENTITY_ENDPOINT", "MSI_ENDPOINT", "WEBSITE_SITE_NAME")
        if any(os.getenv(name) for name in azure_identity_markers):
            return AzureAuthMode.MANAGED_IDENTITY
        return AzureAuthMode.AZURE_CLI

    def _validate_workload_identity(self) -> None:
        missing = [
            name
            for name, value in (
                ("AZURE_TENANT_ID", self.settings.tenant_id),
                ("AZURE_CLIENT_ID", self.settings.client_id),
                ("AZURE_FEDERATED_TOKEN_FILE", self.settings.federated_token_file),
            )
            if not value
        ]
        if missing:
            raise AzureAuthenticationError(
                f"workload_identity requires: {', '.join(missing)}"
            )
        if not Path(self.settings.federated_token_file).is_file():
            raise AzureAuthenticationError("AZURE_FEDERATED_TOKEN_FILE does not exist")

    @staticmethod
    def _load_identity() -> Any:
        try:
            import azure.identity as identity
        except ImportError as error:
            raise AzureAuthenticationError(
                "Azure authentication support is optional. Install with: pip install -e '.[azure]'"
            ) from error
        return identity


__all__ = [
    "AzureAuthenticationError",
    "AzureAuthMode",
    "AzureAuthSettings",
    "AzureCredentialFactory",
]
