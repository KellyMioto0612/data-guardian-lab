"""Environment-backed application settings."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    data_provider: str = os.getenv("DATA_PROVIDER", "demo")
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")
    azure_client_secret: str = os.getenv("AZURE_CLIENT_SECRET", "")
    synapse_workspace: str = os.getenv("SYNAPSE_WORKSPACE", "")


settings = Settings()
