# Foundation — Architecture Index

> **Status:** Foundation Frozen (DEV-009 → DEV-016)

## Sumário

- [Visão geral](#visão-geral)
- [Objetivo da Foundation](#objetivo-da-foundation)
- [Fluxo arquitetural](#fluxo-arquitetural)
- [Princípios](#princípios)
- [Roadmap congelado](#roadmap-congelado)
- [Documentação relacionada](#documentação-relacionada)

## Visão geral

O Data Guardian Lab fornece observabilidade explicável para ativos de dados. A Foundation define os modelos imutáveis, o parser SQL, o grafo de dependências e as métricas estruturais que serão consumidos pelas camadas posteriores.

A Foundation não implementa Registry, Dashboard, DGI, persistência, integração GitHub ou Semantic Hash.

## Objetivo da Foundation

Estabelecer contratos públicos estáveis para transformar SQL em estruturas determinísticas e analisáveis, sem acoplar parsing, métricas, dependências e futuras integrações de governança.

## Fluxo arquitetural

```text
SQL
 ↓
SQLParser
 ↓
ParsedSQL
 ├── SQLMetricsCalculator
 ├── DependencyGraphBuilder
 ├── GuardianObjectFactory (futuro)
 ├── ObservationFactory (futuro)
 └── SQLScanner (futuro)
```

Os contratos dos componentes estão descritos em [contracts.md](contracts.md), [parser.md](parser.md), [dependency-graph.md](dependency-graph.md) e [metrics.md](metrics.md).

## Princípios

- **Imutabilidade:** modelos públicos são frozen e suas coleções expostas são tuplas ou mappings protegidos.
- **Contratos estáveis:** consumidores dependem dos modelos, não de detalhes internos de implementação.
- **IDs determinísticos:** o mesmo objeto estrutural produz o mesmo identificador.
- **Separação de responsabilidades:** parser, métricas e grafo possuem responsabilidades independentes.
- **Semantic Hash fora do escopo:** `semantic_hash` e geração de hashes permanecem reservados para evolução futura.
- **Determinismo:** agregações são ordenadas quando a ordem não possui significado semântico.

## Roadmap congelado

| CASE | Status |
|---|---|
| DEV-009 | ✅ |
| DEV-011 | ✅ |
| DEV-012 | ✅ |
| DEV-013 | ✅ |
| DEV-014 | ✅ |
| DEV-015 | ✅ |
| DEV-016 | ✅ |
| DEV-016A | ✅ |
| DEV-016B | ✅ |
| DEV-016C | ✅ |
| DEV-016D | 📄 |

O próximo passo de implementação é o DEV-017, dedicado à cobertura do SQL Metrics Calculator.

## Documentação relacionada

- [Contratos públicos](contracts.md)
- [Parser SQL](parser.md)
- [Dependency Graph](dependency-graph.md)
- [Métricas SQL](metrics.md)
