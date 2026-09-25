"""Unit tests for explicit, secretless Azure credential selection."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config.azure_auth import (
    AzureAuthenticationError,
    AzureAuthMode,
    AzureAuthSettings,
    AzureCredentialFactory,
)


class _Credential:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


@pytest.fixture
def factory(monkeypatch: pytest.MonkeyPatch) -> type[AzureCredentialFactory]:
    identity = SimpleNamespace(
        AzureCliCredential=_Credential,
        ManagedIdentityCredential=_Credential,
        WorkloadIdentityCredential=_Credential,
    )
    monkeypatch.setattr(AzureCredentialFactory, "_load_identity", staticmethod(lambda: identity))
    return AzureCredentialFactory


def test_cli_is_the_safe_default_outside_azure(factory: type[AzureCredentialFactory]) -> None:
    credential = factory(AzureAuthSettings()).create()
    assert isinstance(credential, _Credential)
    assert credential.kwargs == {}


def test_managed_identity_uses_only_non_secret_client_id(
    factory: type[AzureCredentialFactory],
) -> None:
    credential = factory(
        AzureAuthSettings(mode=AzureAuthMode.MANAGED_IDENTITY, client_id="public-client-id")
    ).create()
    assert credential.kwargs == {"client_id": "public-client-id"}


def test_auto_selects_managed_identity_in_azure(
    factory: type[AzureCredentialFactory], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDENTITY_ENDPOINT", "http://managed-identity-endpoint")
    credential = factory(AzureAuthSettings()).create()
    assert isinstance(credential, _Credential)


def test_workload_identity_requires_platform_values(
    factory: type[AzureCredentialFactory],
) -> None:
    with pytest.raises(AzureAuthenticationError, match="AZURE_TENANT_ID"):
        factory(AzureAuthSettings(mode=AzureAuthMode.WORKLOAD_IDENTITY)).create()


def test_workload_identity_uses_federated_token_file(
    factory: type[AzureCredentialFactory], tmp_path: Path
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("temporary platform token", encoding="utf-8")
    credential = factory(
        AzureAuthSettings(
            mode=AzureAuthMode.WORKLOAD_IDENTITY,
            tenant_id="tenant-id",
            client_id="client-id",
            federated_token_file=str(token_file),
        )
    ).create()
    assert credential.kwargs == {
        "tenant_id": "tenant-id",
        "client_id": "client-id",
        "token_file_path": str(token_file),
    }
