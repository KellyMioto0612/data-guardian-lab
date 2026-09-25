# Homologação de leitura do Synapse

Status: **pendente de workspace e identidade autorizados**. Testes simulados e análise
local não demonstram acesso, RBAC, completude ou mapeamento de estados em ambiente real.

1. Obtenha do responsável um workspace de homologação e permissão mínima para
   consultar execuções de pipelines. Não cole tokens, SQL ou credenciais no repositório.
2. Em uma máquina aprovada, instale as dependências com Python 3.12:
   `python -m pip install -e ".[azure]"`. Autentique-se com `az login`.
3. Configure `DATA_PROVIDER=synapse`, `AZURE_AUTH_MODE=azure_cli` e
   `SYNAPSE_WORKSPACE=<workspace-autorizado>`. Defina uma janela curta por
   `SYNAPSE_LOOKBACK_HOURS` (padrão 24, máximo 168).
4. Execute `python -m streamlit run src/dashboard/app.py` e compare a contagem e os
   estados de execuções com o monitor do workspace para o mesmo intervalo. Confirme
   que não há continuação além do limite de páginas; nesse caso o conector retorna
   erro, em vez de exibir dados incompletos.
5. Registre apenas data, intervalo, contagem por status, permissões testadas e
   resultado. Revise o acesso e encerre a sessão Azure após a validação.

O conector não executa SQL ou altera recursos. Histórico SQLite está desabilitado
por padrão; habilite `GUARDIAN_HISTORY_DB` somente após definir local e retenção
aceitos para os metadados corporativos.
