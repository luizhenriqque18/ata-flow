# Histórico de versões

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

Consulte o [guia MCP](docs/mcp.md) para configurar a segunda máquina, o token,
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
