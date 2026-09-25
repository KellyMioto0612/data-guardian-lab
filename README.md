# Data Guardian Lab

Plataforma Python 3.11–3.12 para observabilidade de dados: coleta sinais de execução, classifica riscos e oferece uma base extensível para investigação assistida por conhecimento.

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

Requer Python 3.11 ou 3.12. O `requirements.lock` e a CI usam Python 3.12; para instalar o lock reproduzível, use essa versão.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
pytest
ruff check .
```

O adaptador de execuções do Synapse já está implementado. As bibliotecas Azure são opcionais na instalação local; para usá-lo, instale `pip install -e ".[azure]"`. A conexão com um workspace autorizado ainda precisa ser homologada.

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

O conector não executa SQL, não altera recursos e consulta no máximo sete dias de execuções.

## Status

Protótipo funcional: monitoramento demonstrativo de pipelines, análise local de arquivos SQL (inventário, evidências, TDI, dependências e priorização) e dashboard. O conector Synapse de somente leitura está implementado e testado com respostas simuladas; ainda não foi homologado em workspace autorizado. Alertas, histórico operacional, investigação com IA e RAG continuam planejados. Consulte [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Princípios

Observabilidade antes de automação, explicabilidade antes de pontuação, contratos pequenos e integrações substituíveis. A plataforma não deve expor dados sensíveis nos logs nem depender de um fornecedor específico.
