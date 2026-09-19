# ADR-001: Provider architecture

- **Status:** Accepted
- **Date:** 2026-09-19

## Context

The dashboard must work locally while the product expands to Azure Synapse and other execution platforms. Coupling the monitor or UI to one SDK would make testing and future integrations expensive.

## Decision

Define an abstract `PipelineProvider` that returns normalized `PipelineRun` dataclasses. Implement a deterministic `DemoProvider` first and isolate Synapse behind its own provider. `GuardianScout` depends only on the abstraction.

## Consequences

Providers own authentication, retries and source-specific mapping. Consumers remain portable and easy to test. The initial Synapse provider intentionally fails clearly until its query adapter is delivered, rather than returning misleading data.
