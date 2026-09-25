"""Azure Synapse connector boundary."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class SynapseConnector:
    workspace: str
    query: Callable[[str], list[dict[str, Any]]]

    def collect(self) -> dict[str, dict[str, Any]]:
        rows = self.query(
            "SELECT metric_name, metric_value, threshold FROM guardian_health_signals"
        )
        return {
            row["metric_name"]: {
                "value": row["metric_value"],
                "threshold": row["threshold"],
                "metadata": {"workspace": self.workspace},
            }
            for row in rows
        }
