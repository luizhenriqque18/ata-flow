# Documentação do AtaFlow

Para instalar e usar a aplicação, comece pelo [README do projeto](../README.md).
Os comandos dos guias devem ser executados a partir da raiz do repositório.

## Guias atuais

| Documento | Conteúdo |
| --- | --- |
| [Contribuição](CONTRIBUTING.md) | Ambiente, estrutura do código, testes e navegação no editor. |
| [Protocolo de desenvolvimento](development-workflow.md) | Etapas, validação, commits e publicação de versões. |
| [Arquivos locais e migração](storage.md) | Dados, backups, conflitos, `ATAFLOW_HOME` e atalhos. |
| [Servidor MCP](mcp.md) | Acesso aos resumos por stdio e HTTP e configuração dos clientes. |
| [Histórico de versões](CHANGELOG.md) | Mudanças publicadas e melhorias em desenvolvimento. |
| [Instruções para agentes](../AGENTS.md) | Convenções aplicáveis a todo o repositório. |

## Arquitetura

- [ADR-001: código em src e dados locais separados](architecture/adr-001-directory-layout.md).

## Referências de apoio

- [Skills sugeridas para desenvolvimento](skills_recomendadas_projeto.md).
  A disponibilidade depende do ambiente; consulte as skills da sessão atual.

## Registros históricos

Estes documentos preservam propostas e implementações anteriores. Para os
comandos, caminhos e requisitos atuais, use os guias acima.

- [Design original da CLI](history/design-original.md).
- [Walkthrough da primeira refatoração](history/walkthrough.md).
