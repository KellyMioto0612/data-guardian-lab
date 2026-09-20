# Foundation — Dependency Graph

> **Status:** Foundation Frozen (DEV-009 → DEV-016)

## Sumário

- [Responsabilidade](#responsabilidade)
- [Componentes](#componentes)
- [Tipos de nós](#tipos-de-nós)
- [Tipos de arestas](#tipos-de-arestas)
- [Métricas](#métricas)
- [Ciclos](#ciclos)
- [Referências](#referências)

## Responsabilidade

O Dependency Graph representa relações estruturais entre entidades SQL, CTEs, tabelas e procedures chamadas. Ele é construído a partir de `ParsedSQL`, sem persistência ou Registry.

## Componentes

- **DependencyNode:** identidade e atributos de um nó.
- **DependencyEdge:** relação direcionada entre dois nós, com tipo e metadata.
- **DependencyGraph:** coleção imutável de nós, arestas e métricas derivadas.
- **DependencyGraphBuilder:** converte modelos do parser em um grafo determinístico.

## Tipos de nós

```text
procedure
view
sql_script
cte
table
```

Os IDs usam prefixos estáveis, por exemplo `procedure:dbo.refresh_orders`, `table:sales.orders` e `cte:<owner_id>:recent_orders`.

## Tipos de arestas

- `CALLS`: uma entidade chama uma procedure.
- `READS`: uma entidade ou CTE lê uma tabela.
- `WRITES`: uma entidade escreve em uma tabela.
- `JOINS`: uma entidade realiza JOIN com um alvo.
- `DEPENDS_ON`: uma entidade ou CTE depende de outro nó.

```text
procedure:dbo.refresh_orders ──READS────▶ table:sales.orders
procedure:dbo.refresh_orders ──CALLS────▶ procedure:dbo.validate
procedure:dbo.refresh_orders ──DEPENDS_ON▶ cte:...:recent_orders
```

Arestas são deduplicadas por `(source_id, target_id, edge_type)` e nós por `node_id`.

## Métricas

- **fan_out_by_node:** quantidade de destinos distintos por nó, considerando `READS`, `WRITES`, `CALLS`, `DEPENDS_ON` e `JOINS`.
- **called_procedures:** procedures chamadas por cada entidade, com IDs determinísticos.
- **cte_reuse:** relação de reutilização ou ocorrência de CTEs por owner.
- **shared_tables:** tabelas consumidas por mais de um owner.
- **max_dependency_chain:** maior cadeia de dependências observada.

As coleções públicas são imutáveis e ordenadas quando a ordem não possui significado semântico.

## Ciclos

A travessia DFS é protegida contra recursão infinita por controle de caminho/visitados. Ciclos encontrados são registrados como tuplas imutáveis em:

```text
DependencyGraph.metadata["cycles"]
```

O registro de um ciclo não impede a construção do restante do grafo.

## Referências

- [Índice da Foundation](foundation.md)
- [Contratos](contracts.md)
- [Parser](parser.md)
- [Métricas](metrics.md)
