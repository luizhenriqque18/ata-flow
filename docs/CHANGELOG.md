# Histórico de versões

## Em desenvolvimento

- Guia de contribuição e histórico de versões reunidos em `docs/`, com índice
  de navegação em `docs/README.md` e referências atualizadas.
- Design original e walkthrough separados em `docs/history/` como registros
  históricos; os guias atuais continuam destacados no índice.
- Configuração do VS Code oculta `.cache/` e `.venv/` no explorador, mantendo
  os diretórios disponíveis para as ferramentas.

## 2.2.0 — 2026-11-25

### Organização dos diretórios e comandos

- Código movido para `src/ataflow`, `src/agy_tui` e `src/agy_voice`, com
  empacotamento dos três pacotes e do tema Textual.
- Novas entradas `uv run ataflow` e `python -m ataflow`. O alias `transcriber`
  e os adaptadores `main.py` e `ataflow_mcp.py` continuam disponíveis.
- Ícones em `assets/`, utilitários de atalho em `scripts/` e documentação de
  apoio em `docs/`. Caches e temporários centralizados em `.cache/`.

### Dados locais e migração

- Transcrições, atas, preferências e logs passam a ficar em `var/`, ignorado
  pelo Git. O `.env` permanece na pasta base da aplicação.
- Migração automática preserva os favoritos, o token MCP e o significado dos
  caminhos compartilhados. Conflitos ou configurações inválidas interrompem a
  migração sem sobrescrever arquivos; falhas de escrita desfazem os movimentos.
- Caminhos estáveis mesmo ao executar em outro diretório, com opção de escolher
  a pasta base por `ATAFLOW_HOME`. Conexões MCP antigas com `--config` na raiz
  continuam reconhecidas.

### Qualidade automática

- Ruff 0.17.6 incluído nas dependências de desenvolvimento e no lockfile, com
  versão exigida para manter o mesmo padrão entre ambientes.
- GitHub Actions verifica lint, formatação, testes e geração do wheel em
  Windows com Python 3.12, em pushes na main e pull requests.
- Testes incluem migração de dados, execução fora da raiz, adaptadores legados
  e comandos instalados. Áudio e Gemini são simulados; o protocolo MCP é
  validado localmente por stdio e HTTP.
- Validação local: 133 testes aprovados e 1 teste de symlink ignorado por
  limitação do Windows, com lint, formatação e construção do wheel aprovados.

### Atualização

Feche instâncias antigas e reinicie os clientes MCP após atualizar. Execute
`git pull --ff-only`, `uv sync` e `uv run ataflow`. Para desenvolvimento, use
`uv sync --extra dev`. Consulte [o guia de dados](storage.md) para backups, conflitos e
configurações personalizadas. O atalho pode ser atualizado com
`scripts/criar_atalho.bat`.

Esta versão incrementa o número secundário por reunir novos comandos e migração
de diretórios mantendo as entradas anteriores de execução.

## 2.1.1 — 2026-11-25

### Encerramento completo da gravação

- A sessão aguarda a captura parar, processa o áudio pendente e o último bloco
  incompleto, e conclui a escrita da transcrição antes de liberar a geração da ata.
- A saída por `Ctrl+C` também aguarda a finalização da sessão.
- Filas cheias aguardam espaço, sem descartar blocos de áudio pendentes.
- Falhas do Whisper e de escrita interrompem o fluxo automático de geração da
  ata e preservam o texto já salvo, em vez de serem tratadas como ausência de fala.

### Organização do código

- Geração de atas extraída para `GenerateMeetingSummary`, um serviço independente
  da interface, com leitura da transcrição e gravação atômica do Markdown.
  Uma falha preserva a transcrição e uma eventual ata anterior.
- O `SessionManager` recebe explicitamente uma implementação de `STTStrategy`.
  A deduplicação de texto sobreposto foi movida para `agy_voice/processing.py`;
  o gerenciador não importa mais o backend Whisper.
- Os testes legados foram atualizados para os contratos atuais de transcrição.

### Validação e atualização

- Suíte completa: 113 testes aprovados e 1 teste de symlink ignorado por limitação
  do Windows. Testes de gravação usam áudio e STT simulados; testes de geração de
  atas usam um provedor simulado, sem chamadas reais ao Gemini.
- Ruff e formatação aprovados nos módulos alterados e seus testes.
- Atualize o código com `git pull --ff-only`, execute `uv sync` e inicie com
  `uv run python main.py`.
- Integrações Python que criam sessões devem fornecer `stt=...`, aguardar
  `session.start(...)` e finalizar com `await session.finish()`.

## 2.1.0 — 2026-10-28

### Resumos disponíveis para outros chats pelo servidor MCP

O AtaFlow agora permite que clientes MCP consultem resumos de reuniões para
compor o contexto de uma conversa ou preparar e-mails com decisões e pendências.
Não é necessário copiar manualmente os arquivos Markdown para cada chat.

- **Acesso local via stdio:** o cliente inicia o servidor, sem carregar áudio,
  Whisper ou Gemini e sem exigir que a interface de gravação esteja aberta.
- **Acesso pela rede via Streamable HTTP:** outro computador pode consultar o
  endpoint `/mcp`, com IP de escuta, porta e endereço do servidor configuráveis.
- **Nova tela Servidor MCP:** ativação e desativação do acesso, escolha da pasta,
  limites de busca/leitura e configurações de conexão para Codex e outros clientes.
- **Autenticação na rede:** token obrigatório, com geração, cópia e troca pela
  interface. O token não é incluído automaticamente nas configurações exportadas.
- **Controle do servidor HTTP:** inicia ao salvar uma configuração ativa e ao
  abrir o AtaFlow; encerra ao desativar o acesso ou fechar a interface. Também
  pode ser executado separadamente pela linha de comando.
- **Busca e leitura com paginação:** ferramentas `search_summaries` e
  `read_summary`, com indicação explícita da próxima página.

### Acesso e privacidade

O acesso começa desativado e é somente de leitura. Apenas arquivos
`*-resumo.md` diretamente na pasta compartilhada são disponibilizados;
transcrições brutas, áudio e credenciais da aplicação não são expostos.
Todas as instâncias verificam as preferências nas próximas chamadas. Trocar o
token revoga o anterior nas próximas requisições HTTP. Conteúdo já obtido por
um chat permanece nesse chat.

HTTP deve ser usado em LAN confiável ou VPN; ele não cifra o conteúdo nem o
token. Para redes não confiáveis, use VPN ou proxy HTTPS. O AtaFlow não altera
o firewall automaticamente nem envia e-mails por conta própria.

### Atualização e uso

Esta release também inclui as melhorias de modelos Gemini já presentes na
branch principal desde a `v2.0.0`: catálogo de modelos, favoritos, escolha do
modelo padrão, testes de disponibilidade e padronização dos botões da interface.

Execute `uv sync`, abra `uv run python main.py` e selecione **Servidor MCP**.
O modo stdio permanece disponível junto do acesso pela rede. Preferências
locais antigas recebem os novos campos com acesso de rede desativado.

Para executar o HTTP sem a interface, depois de configurar e ativar o acesso:

```powershell
uv run python ataflow_mcp.py --transport streamable-http
```

Consulte o [guia MCP](mcp.md) para configurar a segunda máquina, o token,
o Codex e o Windows Firewall. O servidor independente precisa permanecer em
execução; ele não instala um serviço automático do Windows.

A versão do pacote e do README foi alinhada à sequência de releases do GitHub:
`2.1.0`, após a release `v2.0.0` (os metadados antigos ainda indicavam `0.2.0`).

### Validação

- 75 testes passaram e 1 teste de symlink foi ignorado por limitação do Windows,
  excluindo os arquivos legados `tests/test_transcriber.py` e
  `tests/test_session_manager.py`, que já apresentam incompatibilidades com a
  implementação atual.
- Testes incluem protocolo MCP real por stdio e HTTP, autenticação, troca de
  token, bloqueio por Host/Origin, conflito de porta e ciclo de vida do servidor.
- Verificação Ruff dos módulos MCP e seus testes, lockfile e geração do wheel.
- Conexão a partir de uma segunda máquina depende da rede/firewall do usuário;
  os testes automatizados de HTTP usam conexões locais.
