# Segurança operacional

O scanner apenas lê arquivos locais permitidos e analisa o conteúdo em memória. Ele não abre
conexões com bancos, não executa SQL e não envia conteúdo a serviços externos.

## Dados e logs

- Use somente fixtures sintéticos em `tests/fixtures/sql`.
- Não versione dumps, SQL corporativo, backups `*.bak` ou inventários de máquina.
- Erros do scanner identificam somente a classe da exceção; o conteúdo SQL é omitido.
- Avisos do parser de terceiros são suprimidos para impedir a divulgação de trechos de SQL em
  console ou CI.

## Dependências

Instale a partir do arquivo de lock para reproduzir as versões verificadas em CI:

```powershell
python -m pip install -r requirements.lock
```

## Autenticação Azure sem segredos

O projeto não aceita client secret, senha SQL, token estático ou certificado no código.

- Desenvolvimento local: `AZURE_AUTH_MODE=azure_cli` e login interativo via `az login`.
- Recursos Azure: `AZURE_AUTH_MODE=managed_identity`; `AZURE_CLIENT_ID` é opcional e identifica
  uma identidade gerenciada atribuída pelo usuário.
- CI/Kubernetes: `AZURE_AUTH_MODE=workload_identity`; a plataforma fornece o arquivo de token OIDC
  efêmero, `AZURE_TENANT_ID` e `AZURE_CLIENT_ID`.

O modo `auto` seleciona Workload Identity quando existe token federado, Managed Identity quando o
ambiente Azure anuncia seu endpoint de identidade e Azure CLI nos demais casos. A camada só cria a
credencial; ela não solicita token nem abre conexão até um conector chamar a API correspondente.

## Leitura do Synapse

O conector de pipelines usa apenas a operação de consulta de execuções do endpoint de desenvolvimento
do workspace. Ele não executa SQL, não altera pipelines, limita a consulta a até sete dias e a dez
páginas, aplica timeout e omite tokens e respostas de erro dos resultados e logs.

Para homologar, conceda somente a permissão necessária para consultar execuções de pipeline à
identidade do Guardian. Não conceda permissões de criação, alteração, exclusão ou administração.
