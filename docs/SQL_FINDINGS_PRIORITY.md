# Prioridade dos achados SQL

Os sinais do analisador indicam onde revisar; não demonstram, por si só, defeito em produção. A severidade abaixo representa o impacto potencial caso a condição seja confirmada. O arquivo de origem e a implantação real precisam ser conferidos antes de qualquer alteração em SQL operacional.

| Prioridade | Achado | Impacto possível | Próxima ação |
| --- | --- | --- | --- |
| Alta | Definição de view com `ORDER BY` sem `TOP`/`OFFSET`, ou consulta adicional sem separador de lote | A criação da view pode falhar; o resultado pode não corresponder ao contrato esperado | Separar consultas de validação do DDL e testar `CREATE VIEW` em ambiente autorizado. Não executar automaticamente no banco. |
| Alta | SQL-010, escrita sem filtro; SQL-004, `EXEC` dinâmico **dentro** do objeto | Alteração ampla de dados, ou comportamento difícil de auditar | Conferir o corpo do objeto e sua intenção; planejar correção com o responsável. |
| Média | SQL-001, `SELECT *` (inclusive `alias.*`) na saída de view; `UNION ALL SELECT *` | Mudança de colunas ou ordem pode quebrar consumidores | Explicitar colunas e comparar esquema e ordem com consumidores. |
| Média | SQL-002/003, `JOIN` cartesiano ou sem condição; SQL-006, complexidade alta | Multiplicação de linhas, custo ou dificuldade de manutenção | Verificar cardinalidade, filtros e plano de execução. |
| Baixa | SQL-005, fallback do parser; SQL-007/008, padrões de subconsulta e tabela temporária; SQL-009, documentação ausente | Redução da confiança na análise ou esforço de manutenção | Revisar manualmente; não tratar como erro de produção sem evidência adicional. |

**Limites da validação:** regras estáticas não comprovam que um script foi implantado nem medem desempenho no Synapse. `SQL-007` conta ocorrências do padrão de subconsulta e não prova aninhamento. O TDI é um indicador heurístico sem calibração com incidentes reais; não deve ser apresentado como probabilidade de falha. O relatório agregado do scanner apresenta contagens por regra e severidade, sem publicar código SQL, nomes ou caminhos do corpus privado.

**Ordem recomendada:** (1) homologar a criação das views suspeitas; (2) confirmar escritas e execução dinâmica no corpo dos objetos; (3) explicitar saídas públicas e uniões posicionais; (4) revisar custo e qualidade dos dados; (5) tratar documentação e cobertura do parser. A conexão Synapse ainda exige workspace e identidade autorizados, conforme [roteiro de validação](SYNAPSE_VALIDATION.md).
