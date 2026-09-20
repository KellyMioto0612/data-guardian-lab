# Foundation — Public Contracts

> **Status:** Foundation Frozen (DEV-009 → DEV-016)

## Sumário

- [Escopo](#escopo)
- [ScanResult](#scanresult)
- [RepositoryScanResult](#repositoryscanresult)
- [Registry conceitual](#registry-conceitual)
- [Regras de estabilidade](#regras-de-estabilidade)
- [Referências](#referências)

## Escopo

Este documento é a referência dos contratos públicos da Foundation. Ele descreve os objetos de resultado que conectam parsing, análise e futuras camadas de governança. O fluxo estrutural de entrada está em [parser.md](parser.md); as métricas e dependências estão em [metrics.md](metrics.md) e [dependency-graph.md](dependency-graph.md).

## ScanResult

`ScanResult` representa o resultado de uma unidade de análise, normalmente um arquivo ou ativo SQL.

### Finalidade

- associar o resultado ao objeto analisado;
- transportar observações, métricas, dependências e provenance;
- informar sucesso, falhas recuperáveis e erros do scan.

### Invariantes

- o resultado identifica sua origem;
- coleções públicas são imutáveis;
- erros não devem ser confundidos com ausência de observações;
- o status representa o estado final da unidade analisada.

### GuardianObject

Representa a identidade governável do ativo: tipo, nome qualificado, identificadores determinísticos, plataforma, schema, database, tags e metadata.

### Observation

Representa uma observação produzida sobre um `GuardianObject`, incluindo valor, métrica, severidade, contexto e provenance quando aplicável.

### Provenance

Registra de onde o resultado veio: arquivo, origem, localização, modo de parsing, versão ou outros dados de rastreabilidade disponíveis.

### ScanError

Representa uma falha associada ao scan. Deve preservar mensagem, classificação e contexto sem invalidar silenciosamente o resultado.

### ScanStatus

Representa o estado do scan, como concluído, concluído com avisos ou com erro. Os consumidores devem tratar o status como contrato, não inferi-lo pela existência de listas.

## RepositoryScanResult

`RepositoryScanResult` agrega vários `ScanResult` de um repositório ou unidade de execução.

### Responsabilidades

- agrupar resultados individuais;
- preservar provenance da execução;
- expor erros e avisos agregados;
- fornecer uma visão consistente do escopo analisado.

### Propriedades derivadas

Podem ser derivadas de seus resultados: contagem de arquivos, contagem de objetos, contagem de erros, contagem de avisos e métricas agregadas. Propriedades derivadas não devem alterar os resultados individuais.

## Registry conceitual

A Foundation somente define que objetos e observações devem possuir identidade estável e ser consumíveis por um Registry futuro. A implementação do Guardian Registry está fora do escopo desta documentação.

## Regras de estabilidade

> **Nenhum contrato público desta documentação deve ser alterado sem um novo CASE de arquitetura.**

Alterações incompatíveis exigem revisão explícita, atualização da documentação e cobertura correspondente.

## Referências

- [Índice da Foundation](foundation.md)
- [Parser](parser.md)
- [Dependency Graph](dependency-graph.md)
- [Métricas](metrics.md)
