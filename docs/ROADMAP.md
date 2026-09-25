# Roadmap

## Situação atual

O Data Guardian possui análise local de SQL, evidências, TDI, lineage, inventário
priorizado e dashboard. A integração de operações do Synapse está pronta em código,
com consulta limitada e somente leitura. A única etapa pendente dessa frente é a
homologação contra o workspace autorizado.

## Concluído

- [x] Contratos, classificação de risco e fundação de observabilidade.
- [x] Abstração de provedores e modelo normalizado de `PipelineRun`.
- [x] Dataset demonstrativo e `GuardianScout` independente de provedor.
- [x] Dashboard Streamlit com KPIs, séries diárias e filtros.
- [x] Scanner SQL seguro: inventário de procedures/views, evidências e TDI.
- [x] Lineage, impacto downstream, similaridade e ranking de prioridade técnica.
- [x] Autenticação Azure sem segredo hardcoded (Azure CLI, managed identity ou
  workload identity).
- [x] Adaptador Synapse de somente leitura para execuções de pipeline, com janela
  temporal limitada e testes automatizados.

## Em homologação — Operação Synapse

- [ ] Executar a primeira consulta de somente leitura no workspace autorizado.
- [ ] Validar permissões mínimas, conectividade e o mapeamento de estados retornados.
- [ ] Registrar a evidência de homologação sem persistir token, SQL ou dados sensíveis.

## Próximo incremento — Sinais operacionais

- [ ] Integrar métricas de execução via Azure Monitor / Synapse, mantendo coleta
  somente leitura e escopo mínimo.
- [ ] Adicionar telemetria estruturada do próprio Guardian (sucesso, falha, latência
  e contagem), sem conteúdo de consultas ou credenciais.
- [ ] Persistir histórico de execuções em armazenamento aprovado e definir retenção.
- [ ] Configurar regras de SLA e alertas com destinatários, limiares e processo de
  resposta aprovados.

## Evolução de governança

- [ ] Definir RBAC de produção e migrar a execução agendada para managed identity.
- [ ] Estabelecer processo para mover ou eliminar o conteúdo da quarentena privada.
- [ ] Revisar periodicamente dependências, permissões e evidências de auditoria.
