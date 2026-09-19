# Arquitetura

## Visão geral

O Data Guardian Lab é organizado em camadas com fluxo unidirecional:

```text
fonte de dados -> connector -> monitor/scout -> analyzer -> alerta/relatório
                                      |
                                      +-> eventos para RAG (futuro)
```

### `connectors`
Responsável por autenticar, consultar e normalizar sinais de sistemas externos. O restante da aplicação recebe modelos Python simples, sem conhecer SDKs específicos. A primeira implementação é o Azure Synapse.

### `monitor`
Orquestra sondagens de saúde e converte respostas dos conectores em observações. Um scout deve ser barato, idempotente e seguro para execução frequente.

### `analyzers`
Aplica regras determinísticas aos sinais normalizados. A classificação deve explicar quais evidências levaram ao nível de risco; modelos estatísticos ou LLMs podem complementar as regras, mas não substituí-las silenciosamente.

### `rag`
Espaço reservado para indexação e recuperação de runbooks, contratos, lineage e incidentes. Conteúdo recuperado deverá ser rastreável à fonte.

## Contratos fundamentais

- **Observation**: `metric`, `value`, `threshold` e contexto operacional.
- **RiskAssessment**: `level`, `score`, `reasons` e metadados da origem.
- **Connector**: consulta uma fonte e retorna dados serializáveis, sem vazar credenciais.

## Confiabilidade e segurança

- Timeouts, retries limitados e circuit breaker pertencem ao conector.
- Logs devem conter IDs de execução e nomes de objetos, nunca tokens ou payloads completos.
- Configuração vem do ambiente ou de um secret manager; não é versionada.
- Cada alerta precisa de evidência, timestamp e link para a execução original.
