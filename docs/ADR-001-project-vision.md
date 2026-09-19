# ADR-001: Visão do projeto

- **Status:** Aceito
- **Data:** 2026-09-19
- **Decisores:** equipe Data Guardian Lab

## Contexto

Falhas de pipelines são descobertas tarde e exigem investigação manual espalhada por logs, catálogos e runbooks. Precisamos de uma base pequena que possa observar plataformas de dados sem acoplar a lógica de negócio a um fornecedor.

## Decisão

Construir uma plataforma Python 3.11 orientada a contratos, com três responsabilidades separadas: conectores coletam sinais, scouts orquestram observações e analyzers classificam risco. A classificação inicial será determinística e explicável. Integrações futuras de IA e RAG serão camadas complementares, não a única fonte de decisão.

## Consequências

**Benefícios:** testes unitários simples, troca de plataforma sem reescrever regras e alertas auditáveis.

**Custos:** será necessário manter contratos por conector; regras determinísticas exigirão evolução; persistência, filas e autenticação corporativa ficam para fases posteriores.

## Alternativas rejeitadas

- Começar por um dashboard, pois posterga a qualidade dos sinais.
- Acoplar todos os módulos a um SDK, dificultando testes e expansão.
- Usar um LLM como classificador primário, reduzindo previsibilidade e explicabilidade.
