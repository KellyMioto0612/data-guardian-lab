# Data Guardian Lab architecture

Sprint 2 introduces a provider boundary: providers normalize platform-specific execution data into `PipelineRun`; monitoring and presentation consume only that contract.

```text
provider -> PipelineProvider -> GuardianScout -> dashboard / analyzers
```

`DemoProvider` supplies deterministic local data, while `SynapseProvider` reserves the Azure integration seam. This keeps development and tests independent of cloud credentials. Configuration is environment-backed; the current project does not load Azure client secrets and the future adapter is intended to use managed identity.
