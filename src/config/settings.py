"""Environment-backed application settings."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    data_provider: str = os.getenv("DATA_PROVIDER", "demo")
    # Reserved for a user-assigned managed identity. No client secret is read.
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")
    azure_auth_mode: str = os.getenv("AZURE_AUTH_MODE", "auto")
    synapse_workspace: str = os.getenv("SYNAPSE_WORKSPACE", "")
    synapse_lookback_hours: int = int(os.getenv("SYNAPSE_LOOKBACK_HOURS", "24"))


settings = Settings()
