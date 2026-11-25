# Arquivos locais e migração de diretórios

O código fica em src, os ícones em assets e os utilitários em scripts. Os únicos
scripts Python na raiz são main.py e ataflow_mcp.py, mantidos para compatibilidade.

## Dados locais

No checkout, a pasta base é a raiz do repositório. Os arquivos são organizados em:

```text
var/
├── transcricoes/             # Transcrições .txt e atas *-resumo.md
├── model_preferences.json    # Favoritos, padrão, catálogo e testes Gemini
├── mcp_preferences.json      # Acesso MCP, pasta compartilhada e token
└── logs/
    └── transcriber.log
```

var é ignorado pelo Git e deve ser incluído no seu backup pessoal. O .env continua
na pasta base e não é movido. Caches e temporários de desenvolvimento ficam em
.cache e também são ignorados. Execuções antigas de teste foram preservadas em
.cache/archive; podem ser excluídas quando não forem mais necessárias.

Uma instalação por wheel usa %LOCALAPPDATA%/AtaFlow no Windows. Para escolher
outra pasta, defina ATAFLOW_HOME no ambiente antes de iniciar qualquer processo:

```powershell
$env:ATAFLOW_HOME = 'D:\Dados\AtaFlow'
uv run ataflow
```

A TUI e os processos MCP devem usar a mesma pasta base. Coloque o .env nessa
pasta. A variável ATAFLOW_HOME precisa ser definida no ambiente do processo,
não dentro do próprio .env. Os caminhos não dependem do diretório do terminal.

## Migração de uma instalação existente

Feche versões antigas do AtaFlow e reinicie os clientes MCP após atualizar.
A primeira inicialização migra automaticamente os quatro locais legados da raiz
para var, preservando transcrições, favoritos, resultados dos testes, logs e token.
O caminho da pasta compartilhada é ajustado para continuar apontando para os
mesmos resumos, inclusive quando era relativo ou externo à pasta de transcrições.
Configurações MCP personalizadas fora da raiz não são migradas automaticamente.

Os argumentos antigos --config apontando para mcp_preferences.json da raiz são
reconhecidos e encaminhados à configuração em var. Novas conexões usam
python -m ataflow.mcp.server e o caminho atual das preferências.

Se uma origem e seu destino já existirem, a migração é interrompida antes de mover
qualquer arquivo. Nada é mesclado ou sobrescrito automaticamente. Feche as
instâncias, faça uma cópia de segurança das duas versões e escolha qual manter.
Para transcrições, reúna os arquivos desejados em var/transcricoes, resolvendo
nomes duplicados, e retire a pasta legada da raiz. Para preferências, conserve
uma versão validada em var e arquive a outra fora dos caminhos usados pela aplicação.

Configurações inválidas também bloqueiam a migração e são preservadas para correção.
Falhas durante a movimentação desfazem os movimentos já concluídos. Não altere
esses arquivos com uma instância antiga durante a atualização.

Uma trava var/.migration.lock evita migrações simultâneas. Se uma interrupção
abrupta deixar essa trava, confirme que não há instâncias em execução e verifique
os arquivos legados e novos antes de removê-la e iniciar novamente.

## Atalhos Windows

Atalhos existentes para main.py continuam abrindo a aplicação após uv sync.
Para criar ou atualizar o atalho, inclusive o caminho do ícone, execute
scripts/criar_atalho.bat. O novo atalho usa python -m ataflow e assets/icone.ico.
