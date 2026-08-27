# Contribuindo com o transcriber-local

Obrigado pelo interesse em contribuir! Este documento explica como configurar o ambiente de desenvolvimento e entender a arquitetura do projeto.

## Pre-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes ultrarapido)
- Windows 10/11 (a captura WASAPI e especifica do Windows)

## Configuracao do Ambiente

`powershell
# 1. Clone o repositorio
git clone <URL>
cd transcriber-local

# 2. Instale as dependencias (uv cria o .venv automaticamente)
uv sync --extra dev

# 3. Copie e configure as variaveis de ambiente
copy .env.example .env
# Edite .env e adicione sua GEMINI_API_KEY se for usar o Gemini

# 4. Rode a aplicacao
uv run python main.py
`

## Rodando os Testes

`powershell
# Suite completa
uv run pytest tests/ -v

# Com cobertura de codigo
uv run pytest tests/ --cov=agy_voice --cov=agy_tui --cov-report=term-missing

# Apenas testes de STT
uv run pytest tests/agy_voice/ -v
`

## Linting e Formatacao

Este projeto usa uff para lint e formatacao:

`powershell
# Verificar problemas
uv run ruff check .

# Corrigir automaticamente
uv run ruff check --fix .

# Formatar codigo
uv run ruff format .
`

## Arquitetura

`
transcriber-local/
|-- main.py                   # Ponto de entrada: App Textual
|-- audio_capture.py          # Captura WASAPI (microfone + sistema)
|-- session_manager.py        # Orquestra audio -> STT -> arquivo
|-- summarizer.py             # Resumo LLM (Ollama / Gemini)
|
|-- agy_tui/                  # Biblioteca TUI (reutilizavel em outras ferramentas)
|   |-- app.py                # Classe base AgyApp (herda de textual.App)
|   |-- components.py         # Widgets: TranscriptionLog, ServiceStatusBar, etc.
|   -- theme.tcss            # Design System da plataforma
|
|-- agy_voice/                # Integracao de voz (Strategy Pattern)
|   |-- interfaces.py         # ABCs: STTStrategy, TranscriptionSegment
|   -- stt/
|       -- whisper_local.py  # Provedor: faster-whisper local (CUDA/CPU)
|
-- tests/
    |-- conftest.py           # Fixtures compartilhadas (mocks de hardware)
    |-- agy_voice/            # Testes unitarios do STT
    -- agy_tui/              # Testes dos componentes de UI
`

### Adicionando um Novo Provedor STT

1. Crie um novo arquivo em gy_voice/stt/:
`python
# agy_voice/stt/meu_provedor.py
from agy_voice.interfaces import STTStrategy, TranscriptionSegment
import numpy as np

class MeuSTT(STTStrategy):
    @property
    def sample_rate(self) -> int:
        return 16_000

    def is_available(self) -> bool:
        ...

    def load(self) -> bool:
        ...

    def transcribe(self, audio_data: np.ndarray) -> list[TranscriptionSegment]:
        ...
`

2. Exporte em gy_voice/stt/__init__.py
3. Passe a instancia via --stt na CLI ou diretamente no SessionManager

### Adicionando um Novo Widget ao agy_tui

1. Herde de um widget Textual (Static, Widget, RichLog, etc.)
2. Adicione o widget em gy_tui/components.py
3. Exporte em gy_tui/__init__.py
4. Escreva testes em 	ests/agy_tui/

## Variaveis de Ambiente

Veja .env.example para a lista completa de configuracoes disponiveis.
NUNCA faca commit do arquivo .env — ele ja esta no .gitignore.
