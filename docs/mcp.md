# Resumos do AtaFlow em outros chats

O servidor MCP disponibiliza resumos existentes via **stdio** (na mesma máquina)
ou **Streamable HTTP** (para outro computador). Ambos são somente de leitura,
sem chave Gemini ou necessidade de carregar Whisper. As instâncias consultam a
mesma configuração salva.

## Configurar no AtaFlow

1. Atualize as dependências com `uv sync` e abra `uv run python main.py`.
2. No painel inicial, abra **Servidor MCP**.
3. Escolha a pasta compartilhada (por padrão `transcricoes`), resultados por
   página e caracteres por leitura/busca. A pasta precisa existir. Caminhos
   relativos partem da pasta de `mcp_preferences.json`, não do cliente MCP.
4. Ative **Permitir acesso aos resumos** e clique **Salvar**.
5. Reabra a tela, escolha o formato de conexão e use **Copiar conexão**.

As preferências ficam em `mcp_preferences.json`, ignorado pelo Git. O padrão é
desativado. Cancelar ou pressionar Escape descarta alterações não salvas.
O texto de conexão local usa caminhos absolutos do Python e do projeto atuais;
gere-o novamente se mover a instalação ou trocar o ambiente virtual.

**Desativar e salvar bloqueia as próximas buscas e leituras**, inclusive nas
instâncias conectadas. O processo stdio pertence ao cliente: para encerrá-lo,
desative/remova a conexão também nesse cliente. O servidor HTTP gerenciado pela
interface é encerrado ao desativar o acesso ou ao fechar o AtaFlow.
Textos já recuperados permanecem nos chats.
As alterações de pasta e limites também valem nas próximas chamadas.

## Acessar de outro computador pela rede

Na máquina que contém os resumos:

1. Abra **Servidor MCP** e ative **Permitir acesso aos resumos**.
2. Expanda **Acesso pela rede (HTTP)** e ative a opção de iniciar o servidor.
3. Use `0.0.0.0` como IP de escuta para aceitar conexões IPv4 da rede, ou informe
   o IP de uma interface específica. `127.0.0.1` permite somente acesso local.
4. Escolha a porta, por exemplo `8765`.
5. Informe o IP real ou DNS desta máquina no campo de endereço do cliente, por
   exemplo `192.168.1.10`. Descubra o IPv4 da sua interface com `ipconfig`.
   `0.0.0.0` é endereço de escuta e não deve ser usado no cliente.
6. Clique **Gerar novo token**, **Copiar token** e **Salvar**. Guarde o token no
   outro computador. Não é necessário colá-lo em nenhum chat.
7. Reabra a tela e confira **HTTP ativo**. Selecione **Rede — Codex** ou
   **Rede — outros clientes** e copie a conexão para o outro computador.

O endpoint do exemplo é `http://192.168.1.10:8765/mcp`. A escuta começa ao salvar
e volta a iniciar ao abrir o AtaFlow com o acesso e a rede ativados. Mantenha o
AtaFlow aberto. Não execute simultaneamente o modo independente na mesma porta.
O painel informa erros como porta em uso ou IP inexistente; as preferências
continuam salvas para correção. O indicador mostra se a escuta realmente iniciou.

No **Codex do outro computador**, adicione o trecho gerado ao
`~/.codex/config.toml`, sem duplicar a seção `mcp_servers.ataflow`. Exemplo:

```toml
[mcp_servers.ataflow]
url = "http://192.168.1.10:8765/mcp"
bearer_token_env_var = "ATAFLOW_MCP_TOKEN"
```

Defina `ATAFLOW_MCP_TOKEN` no ambiente que inicia o cliente, com o valor copiado
do AtaFlow, e reinicie o cliente. No PowerShell, para persistir para o usuário:

```powershell
[Environment]::SetEnvironmentVariable("ATAFLOW_MCP_TOKEN", "COLE_O_TOKEN_AQUI", "User")
```

Feche e reabra o aplicativo cliente para herdar a variável. Em outros clientes,
use transporte **Streamable HTTP**, a URL e o cabeçalho
`Authorization: Bearer SEU_TOKEN`. O JSON gerado contém um marcador: substitua
`<TOKEN_CONFIGURADO_NO_ATAFLOW>` pelo token no cliente. As configurações de
conexão copiadas não incluem o segredo automaticamente.

O token é obrigatório e armazenado em `mcp_preferences.json`, ignorado pelo Git.
Quem o tiver poderá ler os resumos compartilhados. Não compartilhe esse arquivo.
Gerar outro token e salvar revoga o anterior nas próximas requisições. Salvar
com a rede desativada encerra a escuta gerenciada pela interface, mantendo stdio
disponível se o interruptor geral estiver ativo. Desativar o interruptor geral
bloqueia ambos os modos.

### Conectividade e firewall

Este modo HTTP destina-se a uma LAN confiável ou VPN: HTTP não cifra os resumos
nem o token. Para atravessar uma rede não confiável, use VPN ou um proxy HTTPS.
Não exponha essa porta diretamente na internet. Em um proxy, encaminhe `Host`
para um endereço/porta autorizado na configuração e preserve o token Bearer.
As verificações de Host e Origin do SDK continuam habilitadas.

No cliente Windows, verifique a conexão:

```powershell
Test-NetConnection 192.168.1.10 -Port 8765
```

Se a porta estiver bloqueada pelo Windows Firewall, crie na máquina servidora
uma regra restrita à sua rede privada. Exemplo, em PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "AtaFlow MCP (LAN)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

Adapte IP, porta e rede ao seu ambiente. O AtaFlow não altera o firewall
automaticamente. `401` significa token ausente/incorreto; `503` indica acesso
desativado ou configuração inválida; erro de Host/Origin exige conferir o
endereço do cliente salvo. Abrir `/mcp` no navegador sem token não é um teste de
autenticação válido; use um cliente MCP.

### Executar o HTTP sem abrir a interface

Depois de salvar as preferências, deixe este comando rodando no servidor:

```powershell
uv run python ataflow_mcp.py --transport streamable-http
```

Use `--config CAMINHO` se desejar outro arquivo de preferências. `Ctrl+C` encerra
o processo. Nesse modo, mudanças no token e nos interruptores bloqueiam/liberam
requisições sem reiniciar; mudanças de IP, porta ou endereço do cliente exigem
reiniciar o processo. O comando não instala um serviço automático do Windows.

## Conectar o Codex localmente (stdio)

Na tela do AtaFlow, escolha **Local — Codex (config.toml)**. Adicione o trecho copiado
ao `~/.codex/config.toml` do usuário, preservando as configurações existentes
e evitando duplicar uma seção `mcp_servers.ataflow`. Reinicie a conexão/cliente.

Alternativa pela CLI (PowerShell, executando na pasta do AtaFlow):

```powershell
codex mcp add ataflow -- "$PWD\.venv\Scripts\python.exe" "$PWD\ataflow_mcp.py"
codex mcp list
```

Os argumentos acima usam o arquivo de preferências padrão. Outros clientes que
aceitam `mcpServers` podem usar o formato **Local — outros clientes (JSON)**. Se o cliente
pedir campos separados, preencha `command` e os itens de `args` desse JSON.
O cliente MCP precisa estar instalado no mesmo computador e ter permissão de
ler a pasta escolhida. Não é necessário deixar a interface do AtaFlow aberta.

Documentação oficial: [configuração MCP do Codex](https://developers.openai.com/codex/mcp/)
e [SDK Python MCP v1](https://py.sdk.modelcontextprotocol.io/v1/).

## Usar no chat

- “Busque no AtaFlow os resumos sobre orçamento e use o mais recente como contexto.”
- “Leia o resumo da reunião de ontem e prepare um e-mail com decisões e pendências.”

As ferramentas são `search_summaries(query, offset)` e
`read_summary(summary_id, offset)`. A busca vazia lista resumos, ordenados pelo
nome em ordem decrescente (cronológico no padrão do AtaFlow). A busca consulta
o nome e os primeiros caracteres de cada arquivo, conforme o limite configurado.
As respostas incluem `next_offset`: use-o até receber `null` para percorrer
todas as páginas ou ler um resumo inteiro sem cortes silenciosos.

Somente arquivos `*-resumo.md` diretamente na pasta escolhida são expostos.
Transcrições `.txt`, áudio, `.env`, subpastas e links para arquivos externos não
são compartilhados. Todos os resumos dessa pasta ficam acessíveis ao cliente;
use uma pasta separada com cópias dos resumos desejados para restringir a seleção.
Configuração inválida bloqueia o acesso e preserva o arquivo para correção.

O servidor permite somente leitura e não envia e-mails. O chat pode redigir a
mensagem e usar sua própria integração de e-mail quando você solicitar o envio.
Chats hospedados na nuvem precisam alcançar a URL e suportar essa autenticação;
endereços privados da LAN não ficam acessíveis à nuvem automaticamente.
