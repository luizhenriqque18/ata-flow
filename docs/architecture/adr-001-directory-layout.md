# ADR-001: código em src e dados locais separados

Status: aceita em 2026-11-25.

## Contexto

A raiz mistura módulos Python, dados de reuniões, preferências, imagens e dezenas
de diretórios temporários de validação. Atalhos Windows e clientes MCP existentes
referenciam os scripts main.py e ataflow_mcp.py na raiz.

## Decisão

- Código da aplicação em src/ataflow, dividido entre gravação, atas e MCP.
- Bibliotecas agy_tui e agy_voice mantidas como pacotes separados dentro de src.
- Dados locais em var, com migração das preferências e transcrições existentes.
- Caches e temporários em .cache, ignorados pelo Git.
- Ícones em assets, utilitários em scripts e documentação de apoio em docs.
- Entradas oficiais ataflow e ataflow-mcp, mantendo transcriber como alias.
- main.py e ataflow_mcp.py permanecem como adaptadores de compatibilidade.

## Alternativas e custos

Manter os módulos na raiz exigiria menos mudanças de imports, mas continuaria
misturando código e arquivos de operação. Um pacote único em src/ataflow com as
bibliotecas agy embutidas dificultaria seu uso independente. A estrutura escolhida
mantém três pacotes e exige instalar o projeto, atualizar o empacotamento e testar
as entradas a partir de outro diretório.

Não serão criadas camadas adicionais de repositórios ou interfaces para simples
movimentação de arquivos. Dados existentes não serão sobrescritos em conflitos.
As configurações MCP precisam preservar o significado dos caminhos relativos.

## Validação

Cada etapa deve passar pelos testes afetados e ter um commit próprio. A migração
do código inclui inspeção do wheel e execução das entradas instaladas. A migração
de dados inclui casos de instalações existentes, conflitos e configurações inválidas.

## Atualização: documentação em 2026-11-26

O guia de contribuição e o histórico de versões também ficam em `docs/`, com
um [índice](../README.md). O README e as instruções para agentes permanecem na
raiz. O design original e o walkthrough anterior ficam em `docs/history/`,
identificados como registros históricos.

Essa organização reduz os arquivos versionados da raiz de dez para oito e
agrupa a documentação para navegação. Os links relativos e o protocolo de
desenvolvimento acompanham a mudança. Links externos para os caminhos antigos
podem precisar de atualização; o README aponta para os novos destinos.

A configuração `.vscode/settings.json` oculta `.cache/` e `.venv/` apenas no
explorador do VS Code. Os diretórios continuam nos mesmos locais. Não há mudança
nos dados, nos comandos instalados ou nos adaptadores de compatibilidade.
