# Data Guardian Lab architecture

Sprint 2 introduces a provider boundary: providers normalize platform-specific execution data into `PipelineRun`; monitoring and presentation consume only that contract.

```text
provider -> PipelineProvider -> GuardianScout -> dashboard / analyzers
```

`DemoProvider` supplies deterministic local data. `SynapseProvider` uses a read-only connector to query pipeline runs through Microsoft Entra authentication; its integration with an authorized workspace is still pending validation. This keeps local development and tests independent of cloud credentials. SQL analysis runs locally through the scanner and does not execute SQL against a database. See `docs/ROADMAP.md` for pending operational work.
