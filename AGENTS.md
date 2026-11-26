# Instruções para agentes — AtaFlow

Estas instruções se aplicam a todo o repositório. Pedidos explícitos do usuário
na sessão atual têm prioridade sobre as convenções deste arquivo.

## Começar uma alteração

- Comunique-se em português. Explique as etapas antes de mudanças relevantes.
- Confira `git status --short --branch` e preserve alterações existentes do usuário.
- Leia [CONTRIBUTING.md](CONTRIBUTING.md) e o
  [protocolo de desenvolvimento](docs/development-workflow.md).
- Para organização ou dados locais, consulte a
  [decisão de layout](docs/architecture/adr-001-directory-layout.md) e o
  [guia de migração](docs/storage.md).

## Limites do projeto

- Código em `src/ataflow`, `src/agy_tui` e `src/agy_voice`; testes em `tests/`.
  Dados em `var/`, caches em `.cache/`, ícones em `assets/` e utilitários em `scripts/`.
- Não adicione novos módulos de aplicação na raiz. `main.py` e `ataflow_mcp.py`
  são adaptadores de compatibilidade; preserve as entradas antigas de execução.
- Centralize caminhos em `src/ataflow/paths.py`; preserve a migração e os caminhos
  de configurações MCP existentes. Não sobrescreva dados em conflitos.
- Nunca versione `.env`, tokens, preferências ou reuniões. Testes devem usar dados
  sintéticos e `ATAFLOW_HOME` isolado, como em `tests/conftest.py`.
- Preserve a abstração `STTStrategy`, a finalização completa de `SessionManager`
  antes da ata e o serviço de geração independente da interface. O MCP é de leitura.

## Validação

Execute a partir da raiz, em Windows com Python 3.12+ e uv:

```powershell
uv sync --locked --extra dev
uv run ruff check .
uv run ruff format --check .
```

- A configuração do Ruff em `pyproject.toml` e o `uv.lock` definem o padrão.
- Para alterações funcionais, execute os testes afetados antes de cada commit.
  Exemplo: `uv run pytest tests/test_session_manager.py tests/test_summary_service.py`.
- Antes de uma release, execute `uv run pytest tests/` e
  `uv build --wheel --out-dir .cache/dist`, além de lint e formatação.
- Documentação isolada exige revisão de conteúdo, caminhos, links locais e
  `git diff --check`; não exige repetir testes funcionais sem mudança de código.
- O CI em `.github/workflows/ci.yml` é a referência da validação no GitHub.

## Git e publicação

- Registre cada melhoria lógica concluída e validada em um commit próprio,
  incluindo sua documentação. Não inclua arquivos sem relação com a tarefa.
- Use mensagens com prefixos como `feat:`, `fix:`, `refactor:`, `ci:`, `docs:` e `chore:`.
- Push, tag e release seguem a autorização do usuário para a tarefa. Quando a
  publicação já estiver autorizada, conclua-a sem pedir confirmação novamente.
- Aplique o versionamento descrito em `docs/development-workflow.md`. Não crie
  uma release apenas para registrar instruções ou documentação.
- Ao publicar, aguarde o CI do commit enviado antes de criar a tag e a release.
  Não reescreva tags publicadas nem use push forçado.
- Informe o que mudou, a validação realizada, os commits e o estado da publicação.
