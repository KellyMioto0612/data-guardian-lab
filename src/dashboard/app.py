"""Streamlit dashboard for Data Guardian Lab."""

import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analyzers.asset_inventory import build_asset_inventory, filter_asset_inventory
from src.config.azure_auth import AzureAuthenticationError
from src.config.settings import settings
from src.connectors.synapse_pipeline import SynapseConnectorError
from src.monitor.operational_history import OperationalHistory
from src.pipeline.sql_pipeline import SQLPipeline
from src.providers.base import PipelineProvider
from src.providers.demo_provider import DemoProvider
from src.providers.synapse_provider import SynapseProvider

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_provider() -> PipelineProvider:
    provider_name = os.getenv("DATA_PROVIDER", "demo").lower()
    if provider_name == "synapse":
        return SynapseProvider(
            os.getenv("SYNAPSE_WORKSPACE", ""), lookback_hours=settings.synapse_lookback_hours
        )
    return DemoProvider()


def load_sql_intelligence(scan_path: str | Path | None = None):
    """Run the local, read-only SQL intelligence flow for the dashboard."""
    configured = scan_path or os.getenv("SQL_SCAN_PATH", "tests/fixtures/sql")
    path = Path(configured)
    resolved = path.resolve() if path.is_absolute() else (_PROJECT_ROOT / path).resolve()
    return SQLPipeline().run_directory(resolved)


def technical_debt_rows(result) -> list[dict[str, object]]:
    """Return safe, tabular TDI data without SQL source content."""
    records = build_asset_inventory(result.guardian_objects, result.evidence)
    return [
        {
            "Ativo": item.name,
            "Tipo": item.object_type,
            "TDI": item.tdi_score,
            "Evidências": item.evidence_count,
            "Maior severidade": item.highest_severity.value if item.highest_severity else "none",
            "Similaridades": item.similarity_count,
            "Impacto downstream": item.downstream_impact,
            "Prioridade": item.priority_score,
            "Criticidade": item.criticality,
        }
        for item in records
    ]


def evidence_rows(result) -> list[dict[str, object]]:
    """Return evidence summaries only; SQL expressions are intentionally omitted."""
    return [
        {
            "Regra": item.rule_id,
            "Severidade": item.severity.value,
            "Ativo": item.object_id,
            "Evidência": item.summary,
            "Linha": item.line_start,
        }
        for item in result.evidence
    ]


def render_sql_intelligence() -> None:
    """Render technical-debt and evidence information from the local scanner."""
    st.divider()
    st.header("Inteligência SQL")
    try:
        result = load_sql_intelligence()
    except (OSError, ValueError) as exc:
        st.warning(f"Análise SQL indisponível: {type(exc).__name__}")
        return

    debt_rows = technical_debt_rows(result)
    evidence = evidence_rows(result)
    high = sum(row["Severidade"] in {"high", "critical"} for row in evidence)
    average_tdi = sum(float(row["TDI"]) for row in debt_rows) / len(debt_rows) if debt_rows else 0
    cards = st.columns(4)
    cards[0].metric("Ativos SQL", len(debt_rows))
    cards[1].metric("Evidências", len(evidence))
    cards[2].metric("Evidências altas ou críticas", high)
    cards[3].metric("TDI médio", f"{average_tdi:.1f}/100")

    type_options = sorted({str(row["Tipo"]) for row in debt_rows})
    severity_options = sorted({str(row["Maior severidade"]) for row in debt_rows})
    criticality_options = sorted({str(row["Criticidade"]) for row in debt_rows})
    filters = st.columns(3)
    selected_types = filters[0].multiselect("Tipo de ativo", type_options, default=type_options)
    selected_severities = filters[1].multiselect(
        "Severidade", severity_options, default=severity_options
    )
    selected_criticalities = filters[2].multiselect(
        "Criticidade", criticality_options, default=criticality_options
    )
    records = build_asset_inventory(result.guardian_objects, result.evidence)
    filtered_records = filter_asset_inventory(
        records,
        object_types=set(selected_types),
        severities=set(selected_severities),
        criticalities=set(selected_criticalities),
    )
    filtered_names = {item.name for item in filtered_records}
    filtered_rows = [row for row in technical_debt_rows(result) if row["Ativo"] in filtered_names]
    st.subheader("Inventário e prioridade técnica")
    st.dataframe(pd.DataFrame(filtered_rows), use_container_width=True, hide_index=True)
    st.subheader("Evidências")
    st.dataframe(pd.DataFrame(evidence), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Data Guardian Lab", layout="wide")
    st.title("Data Guardian Lab")
    st.caption("Observabilidade de execuções de pipelines")

    provider_name = os.getenv("DATA_PROVIDER", "demo").lower()
    if provider_name != "synapse":
        st.warning("MODO DEMONSTRAÇÃO: execuções fictícias; não representam pipelines reais.")
    else:
        st.info("Fonte: execuções do workspace Synapse configurado (somente leitura).")

    try:
        runs = build_provider().get_pipeline_runs()
    except (AzureAuthenticationError, SynapseConnectorError) as exc:
        st.error(f"Dados Synapse indisponíveis: {type(exc).__name__}")
        return

    history_path = os.getenv("GUARDIAN_HISTORY_DB")
    if history_path:
        try:
            history = OperationalHistory(history_path)
            history.record(runs, source=provider_name)
            finding = history.investigate(source=provider_name)
            st.subheader("Histórico e alerta local")
            if finding.alert:
                st.warning(
                    f"Alerta: {finding.failed_runs} execução(ões) com falha nas últimas 24 horas."
                )
            st.caption(finding.explanation)
        except (OSError, ValueError, sqlite3.Error) as exc:
            st.warning(f"Histórico local indisponível: {type(exc).__name__}")

    frame = pd.DataFrame([run.to_dict() for run in runs])
    if frame.empty:
        st.info("Nenhuma execução encontrada.")
        return

    selected_statuses = st.multiselect(
        "Status", sorted(frame["status"].unique()), default=sorted(frame["status"].unique())
    )
    filtered = frame[frame["status"].isin(selected_statuses)]
    success_rate = (filtered["status"].eq("Success").mean() * 100) if len(filtered) else 0
    failed = int(filtered["status"].eq("Failed").sum())
    durations = filtered.loc[filtered["duration_seconds"] > 0, "duration_seconds"]

    cards = st.columns(4)
    cards[0].metric("Execuções no período", len(filtered))
    cards[1].metric("Execuções com falha", failed)
    cards[2].metric("Tempo médio", f"{durations.mean() / 60:.1f} min" if len(durations) else "—")
    cards[3].metric("Taxa de sucesso", f"{success_rate:.1f}%")

    daily = (
        filtered.assign(date=pd.to_datetime(filtered["started_at"]).dt.date)
        .groupby("date", as_index=False)
        .size()
    )
    st.subheader("Execuções por dia")
    st.plotly_chart(
        px.bar(daily, x="date", y="size", labels={"size": "Execuções"}), use_container_width=True
    )

    st.subheader("Execuções")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    render_sql_intelligence()


if __name__ == "__main__":
    main()
