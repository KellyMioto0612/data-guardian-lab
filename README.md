# Data Guardian Lab

Plataforma Python 3.11 para observabilidade de dados: coleta sinais de execução, classifica riscos e oferece uma base extensível para investigação assistida por conhecimento.

## Objetivos

- Detectar sinais de degradação em pipelines e tabelas.
- Transformar métricas e eventos em riscos explicáveis e acionáveis.
- Isolar conectores de plataformas de dados da lógica de análise.
- Evoluir para documentação automática e investigação com RAG.

## Estrutura

```text
src/
├── analyzers/       # Classificação e priorização de riscos
├── connectors/      # Integrações com plataformas de dados
├── monitor/         # Sondagem e coleta de sinais
└── rag/             # Base para recuperação de conhecimento

tests/               # Testes automatizados
docs/                # Arquitetura, decisões e roadmap
```

## Desenvolvimento local

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
pip install -e .
pytest
ruff check .
```

## Status

Versão inicial (v0.1): contratos mínimos para monitoramento, conexão com Synapse e classificação determinística de risco. Consulte [`docs/ROADMAP.md`](docs/ROADMAP.md) para os próximos incrementos.

## Princípios

Observabilidade antes de automação, explicabilidade antes de pontuação, contratos pequenos e integrações substituíveis. A plataforma não deve expor dados sensíveis nos logs nem depender de um fornecedor específico.
