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
- [x] Identificação explícita dos dados demonstrativos no dashboard.
- [x] Histórico SQLite local opcional, retenção de 30 dias e alerta visual baseado em falhas.
- [x] Validação local agregada de corpus SQL sem publicar o conteúdo.

## Em homologação — Operação Synapse

- [ ] Executar a primeira consulta de somente leitura no workspace autorizado.
- [ ] Validar permissões mínimas, conectividade e o mapeamento de estados retornados.
- [ ] Confirmar paginação completa e volume de execuções no workspace real.
- [ ] Registrar a evidência de homologação sem persistir token, SQL ou dados sensíveis.

## Próximo incremento — Sinais operacionais

- [ ] Integrar métricas de execução via Azure Monitor / Synapse, mantendo coleta
  somente leitura e escopo mínimo.
- [ ] Adicionar telemetria estruturada do próprio Guardian (sucesso, falha, latência
  e contagem), sem conteúdo de consultas ou credenciais.
- [ ] Aprovar armazenamento e retenção para histórico corporativo (a implementação
  SQLite local é opcional e serve para desenvolvimento e homologação).
- [ ] Configurar regras de SLA, envio de alertas a destinatários e processo de
  resposta aprovados; o alerta atual aparece apenas no dashboard.
- [ ] Implementar investigação assistida por IA após aprovação de plataforma,
  escopo de dados, recuperação de evidências e avaliação de respostas.

## Evolução de governança

- [ ] Definir RBAC de produção e migrar a execução agendada para managed identity.
- [ ] Estabelecer processo para mover ou eliminar o conteúdo da quarentena privada.
- [ ] Revisar periodicamente dependências, permissões e evidências de auditoria.
