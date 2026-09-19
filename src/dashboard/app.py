"""Streamlit dashboard for Data Guardian Lab."""

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from src.providers.base import PipelineProvider
from src.providers.demo_provider import DemoProvider
from src.providers.synapse_provider import SynapseProvider


def build_provider() -> PipelineProvider:
    provider_name = os.getenv("DATA_PROVIDER", "demo").lower()
    if provider_name == "synapse":
        return SynapseProvider(os.getenv("SYNAPSE_WORKSPACE", ""))
    return DemoProvider()


def main() -> None:
    st.set_page_config(page_title="Data Guardian Lab", layout="wide")
    st.title("Data Guardian Lab")
    st.caption("Observabilidade de execuções de pipelines")

    try:
        runs = build_provider().get_pipeline_runs()
    except NotImplementedError as exc:
        st.error(str(exc))
        return

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
    cards[0].metric("Total de pipelines", len(filtered))
    cards[1].metric("Falhas críticas", failed)
    cards[2].metric("Tempo médio", f"{durations.mean() / 60:.1f} min" if len(durations) else "—")
    cards[3].metric("Taxa de sucesso", f"{success_rate:.1f}%")

    daily = filtered.assign(date=pd.to_datetime(filtered["started_at"]).dt.date).groupby(
        "date", as_index=False
    ).size()
    st.subheader("Execuções por dia")
    st.plotly_chart(px.bar(daily, x="date", y="size", labels={"size": "Execuções"}), use_container_width=True)

    st.subheader("Execuções")
    st.dataframe(filtered, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
