# Contribuindo com o AtaFlow

## Ambiente

Requisitos: Windows 10/11, Python 3.12+ e uv. A captura usa WASAPI.

```powershell
uv sync --extra dev
copy .env.example .env
uv run ataflow
```

Configure GEMINI_API_KEY no .env para gerar atas. Nunca versione credenciais,
preferências locais ou arquivos de reuniões.

## Estrutura do código

```text
src/
├── ataflow/
│   ├── cli.py               # App Textual, navegação e argumentos
│   ├── paths.py             # Localização dos arquivos locais
│   ├── recording/
│   │   ├── capture.py       # Captura WASAPI
│   │   └── session.py       # Ciclo de vida e filas de transcrição
│   ├── summaries/
│   │   ├── catalog.py       # Cliente Gemini, catálogo e preferências
│   │   ├── gemini.py        # Prompt e adaptador de geração
│   │   └── service.py       # Caso de uso de geração da ata
│   └── mcp/
│       ├── server.py        # Biblioteca de resumos e protocolo MCP
│       ├── settings.py      # Preferências e configuração de clientes
│       └── network.py       # Ciclo de vida do HTTP
├── agy_tui/                 # Componentes, telas e tema Textual
└── agy_voice/               # Contratos STT e processamento de texto
```

Instale o projeto com uv sync após alterar a estrutura ou os comandos em
pyproject.toml. Os pacotes são importados da instalação, sem modificar sys.path
nos testes. O wheel inclui os três pacotes e o tema TCSS.

As entradas oficiais são `uv run ataflow` e `uv run ataflow-mcp`. O comando
`transcriber` permanece como alias. Os scripts main.py e ataflow_mcp.py na raiz
são adaptadores para atalhos e conexões MCP existentes.

## Testes e ferramentas

```powershell
uv run pytest tests/
uv run pytest tests/ --cov=ataflow --cov=agy_voice --cov=agy_tui
uv run pytest tests/test_session_manager.py tests/test_summary_service.py
uv run python -m ruff check src tests main.py ataflow_mcp.py
uv run python -m ruff format src tests main.py ataflow_mcp.py
uv build --wheel --out-dir .cache/dist
```

Ruff precisa estar instalado no ambiente de desenvolvimento. Os caches do pytest,
Ruff e uv ficam em .cache. O pytest usa .cache/pytest-tmp para arquivos temporários;
para execuções simultâneas, forneça um --basetemp diferente dentro de .cache.
Testes de captura e Gemini usam implementações simuladas. Há também testes reais
do protocolo MCP em stdio e HTTP local, sem ler reuniões do usuário.

## Adicionar um provedor STT

Implemente `agy_voice.interfaces.STTStrategy`: is_available, load, transcribe e
sample_rate. Injete a implementação em `SessionManager(stt=MeuSTT())`. A montagem
atual em ataflow.cli escolhe WhisperLocalSTT; não existe argumento --stt na CLI.

A deduplicação pertence a agy_voice.processing e funciona com qualquer provedor.
Uma lista vazia indica ausência de fala. Erros do modelo devem ser propagados.

## Ciclo de vida da sessão

`await session.start(...)` carrega o STT fora do event loop e inicia produtor e
consumidor em um TaskGroup. `await session.finish()` para a captura, entrega os
últimos callbacks, drena as filas e processa o bloco final incompleto. Somente
após a escrita da transcrição a interface abre a geração de ata. Ctrl+C também
aguarda a finalização. Falhas preservam o texto já salvo e impedem a ata automática.

## Geração de atas e modelos

GenerateMeetingSummary lê a transcrição, chama um gerador injetável e publica o
Markdown atomicamente. A interface apenas chama o serviço e apresenta o resultado.
O cliente Gemini é compartilhado pelo catálogo, pelos testes de disponibilidade
e pela geração. As preferências usam escrita atômica e nunca incluem a chave API.
Ollama não é suportado.

Consulte [o guia MCP](docs/mcp.md) e [a decisão de layout](docs/architecture/adr-001-directory-layout.md).

## Dados e utilitários

Dados locais ficam em `var/`, caches em `.cache/`, ícones em `assets/` e os
scripts de atalho em `scripts/`. A migração legada é implementada em
`src/ataflow/storage.py` e validada com dados sintéticos. Os testes usam uma
pasta `ATAFLOW_HOME` isolada; nunca devem migrar os dados reais do desenvolvedor.
Consulte [o guia de migração](docs/storage.md) antes de alterar os caminhos.
