# Foundation — SQL Parser

> **Status:** Foundation Frozen (DEV-009 → DEV-016)

## Sumário

- [Responsabilidade](#responsabilidade)
- [Componentes](#componentes)
- [Fluxo](#fluxo)
- [Fallback](#fallback)
- [IDs determinísticos](#ids-determinísticos)
- [Fingerprint](#fingerprint)
- [Imutabilidade](#imutabilidade)
- [Referências](#referências)

## Responsabilidade

`SQLParser` transforma SQL em modelos estruturais imutáveis. Ele preserva descoberta parcial quando o parser primário não consegue produzir uma AST completa, sem calcular hashes ou executar responsabilidades de Registry.

## Componentes

- **ParseIssue:** descreve erro ou aviso de parsing, incluindo código, severidade, modo e localização.
- **ParsedTable:** representa tabela referenciada, incluindo database, schema, nome, operação e confiança.
- **ParsedJoin:** representa JOIN, tipo, lados e condição.
- **ParsedCTE:** representa CTE, referências, tabelas e SQL normalizado.
- **ParsedEntity:** representa procedure, view ou script e seus componentes estruturais.
- **ParsedSQL:** documento agregado, entidades, tabelas, CTEs, issues e contagem de statements.

## Fluxo

```text
SQL
 ↓
SQLGlot
 ↓
AST
 ↓
ParsedEntity
 ↓
ParsedSQL
```

O `ParsedSQL` é a entrada comum de [metrics.md](metrics.md) e [dependency-graph.md](dependency-graph.md).

## Fallback

Quando o SQLGlot falha em uma instrução, o parser pode usar descoberta regex conservadora.

- `PARSE-001`: falha do SQLGlot, severidade `error`, modo `ast`.
- `PARSE-002`: fallback regex utilizado, severidade `warning`, modo `regex_fallback`.

| Origem | Score |
|---|---:|
| AST | 1.0 |
| AST parcial | 0.8 |
| Regex | 0.4 |

O fallback não significa que toda a estrutura foi recuperada; o score expressa confiança na origem da descoberta.

## IDs determinísticos

Os identificadores estruturais seguem a composição mais específica disponível:

```text
procedure:dbo.refresh_orders
view:sales.active_orders
table:sales.orders
cte:<owner_id>:recent_orders
```

Database e schema nunca são inferidos quando não estão presentes na entrada.

## Fingerprint

`entity_fingerprint_seed` é uma representação estrutural determinística baseada em tipo, statement, nome qualificado, SQL normalizado, tabelas, CTEs, JOINs, dependências e procedures chamadas.

Ela:

- não é um hash;
- não representa um digest criptográfico;
- é apenas uma semente estrutural para evolução futura;
- deve permanecer igual para a mesma entrada estrutural.

## Imutabilidade

Os modelos são frozen. Coleções públicas são tuplas e mappings são protegidos contra mutação. A ordem original é preservada quando representa a semântica do SQL; coleções sem significado de ordem podem ser normalizadas deterministicamente.

## Referências

- [Índice da Foundation](foundation.md)
- [Contratos](contracts.md)
- [Dependency Graph](dependency-graph.md)
- [Métricas](metrics.md)
