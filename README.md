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
pip install -e ".[dev]"
pytest
ruff check .
```

As bibliotecas Azure permanecem opcionais até a implementação do adaptador Synapse. Quando ele existir, instale `pip install -e ".[azure]"`.

## Synapse em modo somente leitura

O conector consulta apenas execuções de pipelines e usa token Microsoft Entra. Para validação
local em homologação, instale as dependências Azure, faça login interativo e configure a sessão:

```powershell
pip install -e ".[azure]"
az login
$env:DATA_PROVIDER = "synapse"
$env:AZURE_AUTH_MODE = "azure_cli"
$env:SYNAPSE_WORKSPACE = "seu-workspace"
```

O conector não executa SQL, não altera recursos, rejeita janelas acima de sete dias e sinaliza paginação incompleta. Veja [`docs/SYNAPSE_VALIDATION.md`](docs/SYNAPSE_VALIDATION.md) para a homologação.

## Status

Versão inicial (v0.1): contratos mínimos para monitoramento, conexão com Synapse e classificação determinística de risco. Consulte [`docs/ROADMAP.md`](docs/ROADMAP.md) para os próximos incrementos.

## Histórico e alertas locais

Defina `GUARDIAN_HISTORY_DB` com um caminho SQLite aprovado para habilitar histórico opcional com retenção de 30 dias e alerta visual para falhas nas últimas 24 horas. Somente identificador, nome, status, início e duração das execuções são armazenados. Dados de demonstração e Synapse ficam separados. Não há envio de alertas nem diagnóstico automático de causa raiz; a investigação atual apenas resume os fatos observados.

Para validar arquivos SQL autorizados localmente sem imprimir SQL, nomes ou caminhos:

```bash
python -m scripts.validate_sql_corpus /caminho/sql --allowed-root /caminho
```

## Princípios

Observabilidade antes de automação, explicabilidade antes de pontuação, contratos pequenos e integrações substituíveis. A plataforma não deve expor dados sensíveis nos logs nem depender de um fornecedor específico.
