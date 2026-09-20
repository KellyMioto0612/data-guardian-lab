# Foundation — SQL Metrics

> **Status:** Foundation Frozen (DEV-009 → DEV-016)

## Sumário

- [Responsabilidade](#responsabilidade)
- [SQLEntityMetrics](#sqlentitymetrics)
- [SQLMetrics](#sqlmetrics)
- [Métricas documentadas](#métricas-documentadas)
- [Valores especiais](#valores-especiais)
- [Referências](#referências)

## Responsabilidade

O sistema de métricas descreve a complexidade estrutural observável do SQL sem executar o SQL e sem gerar hashes. O parser fornece os dados de entrada conforme [parser.md](parser.md).

## SQLEntityMetrics

`SQLEntityMetrics` representa as métricas de uma entidade individual.

### Grupos

- **Identidade:** nome, tipo e nome qualificado.
- **Statements:** quantidade de statements da entidade.
- **Entidades:** indicadores de procedure, view e script.
- **CTEs:** quantidade, recursividade, nomes e profundidade máxima.
- **JOINs:** quantidade, distribuição em `join_types`, `CROSS JOIN` e JOINs sem condição.
- **Tabelas:** referências, tabelas únicas, tabelas lidas e tabelas escritas.
- **Dependências:** quantidade, dependências distintas e fan-out.
- **Procedures chamadas:** quantidade e coleção normalizada.
- **Parsing:** erros e warnings associados à análise.
- **Campos reservados:** `complexity_score`, `content_hash` e `semantic_hash` permanecem opcionais.

## SQLMetrics

`SQLMetrics` agrega as métricas de todas as entidades de um `ParsedSQL`. A agregação preserva determinismo e não altera a entrada.

O calculator também produz uma coleção de `SQLEntityMetrics`, permitindo navegar do agregado para cada entidade.

## Métricas documentadas

| Métrica | Significado |
|---|---|
| `statement_count` | Quantidade de statements no documento |
| `procedure_count` | Procedures identificadas |
| `view_count` | Views identificadas |
| `script_count` | Scripts identificados |
| `cte_count` | CTEs identificadas |
| `recursive_cte_count` | CTEs marcadas como recursivas |
| `max_cte_depth` | Maior profundidade de referências entre CTEs |
| `join_count` | JOINs identificados |
| `join_types` | Distribuição normalizada por tipo de JOIN |
| `cross_join_count` | JOINs do tipo CROSS |
| `joins_without_condition` | JOINs cujo condition é `None` |
| `table_reference_count` | Total de referências a tabelas |
| `unique_table_count` | Quantidade de tabelas distintas |
| `dependency_count` | Dependências distintas |
| `dependency_fan_out` | Maior fan-out direto encontrado |
| `parse_error_count` | Issues com severidade `error` |
| `warning_count` | Issues com severidade `warning` |

Os tipos de JOIN são normalizados para `INNER`, `LEFT`, `RIGHT`, `FULL`, `CROSS`, `NATURAL` e `UNKNOWN`.

## Valores especiais

| Valor | Significado |
|---|---|
| `0` | Conhecido e igual a zero |
| `None` | Desconhecido ou não calculado |

Os campos abaixo continuam reservados para evolução futura:

- `complexity_score`
- `content_hash`
- `semantic_hash`

Nenhum deles deve ser inferido ou preenchido artificialmente pela Foundation.

## Referências

- [Índice da Foundation](foundation.md)
- [Contratos](contracts.md)
- [Parser](parser.md)
- [Dependency Graph](dependency-graph.md)
