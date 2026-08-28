# 🎙️ AtaFlow (v0.2)
**O seu assistente pessoal e 100% privado para transformar reuniões em atas perfeitas.**

O **AtaFlow** é uma ferramenta de linha de comando com uma **Interface Gráfica no Terminal (TUI)** incrivelmente fluida, desenvolvida em Python. Ele escuta simultaneamente o seu microfone e o áudio do sistema (colegas de trabalho, vídeos, apresentações) e gera uma transcrição em tempo real, operando **100% offline** na sua máquina para garantir privacidade absoluta.

Diga adeus ao trabalho manual de anotar tudo durante as calls!

---

## 🚀 Principais Funcionalidades

- **🖥️ Interface Visual de Terminal (TUI):** Navegue com facilidade. Esqueça a configuração manual de índices de áudio — basta abrir o app e selecionar seus dispositivos com as setas do teclado.
- **🗣️ Diarização Automática:** O sistema identifica e rotula automaticamente quem está falando com as tags `[Você]`, `[Outros]` ou `[Você + Outros]`.
- **🧠 Resumos Inteligentes com IA:** Ao final da reunião, gera uma ata profissional e estruturada em Markdown, destacando pontos principais e decisões. Suporta IA local (**Ollama**) ou em nuvem (**Gemini**).
- **🔒 Privacidade e Performance:** Transcrição feita localmente com o motor **Faster-Whisper** (com suporte à aceleração CUDA para placas NVIDIA). Ninguém ouve suas reuniões além de você.
- **🎛️ Processamento de Áudio Avançado:** Faz o *downmix* (Estéreo -> Mono) e *resample* (para 16kHz) nativamente para garantir a precisão máxima do Whisper e evitar alucinações da IA.

---

## 🛠️ Guia de Instalação Rápida

Configure o AtaFlow no seu Windows em poucos passos:

### 1. Preparar o Ambiente
Usamos o [uv](https://docs.astral.sh/uv/), o gerenciador de pacotes Python ultrarrápido. (Requer Python 3.12+).

```powershell
# Sincroniza e instala todas as dependências isoladamente no .venv
uv sync
```

### 2. Configurações (.env)
Copie o template de configurações e ajuste conforme necessário:

```powershell
copy .env.example .env
```
*(No arquivo `.env`, você pode definir o idioma padrão, escolher entre Gemini/Ollama, etc).*

### 3. Habilitar Aceleração (Apenas Placas NVIDIA)
Para processar o áudio com a sua placa de vídeo (como uma RTX ou GTX), instale as bibliotecas NVIDIA essenciais:

```powershell
uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

### 4. Escolher o Motor de IA para os Resumos

**Modo Ninja (100% Offline com Ollama)**
1. Instale o [Ollama para Windows](https://ollama.com/).
2. Baixe o modelo: `ollama run llama3.2:1b`
3. No seu `.env`, defina `LLM_PROVIDER=ollama`

**Modo Nuvem (Máxima Qualidade com Google Gemini)**
1. No seu `.env`, configure:
```env
GEMINI_API_KEY=sua_chave_aqui
LLM_PROVIDER=gemini
```

---

## 💻 Como Usar no Dia a Dia

Para iniciar a mágica, apenas rode:

```powershell
uv run python main.py
```
*(💡 Dica: Se você usou nosso script `criar_atalho.bat`, basta dar duplo clique no atalho gerado na Área de Trabalho!)*

### 🎮 Fluxo de Uso:
1. **Configuração Rápida:** A tela inicial lista seus microfones e o áudio do sistema (Loopback). Use as setas do teclado e o `Enter` para selecionar.
2. **A Mágica Acontece:** A interface TUI inicia, mostrando a saúde do áudio, o carregamento do Whisper na sua GPU, e a transcrição ao vivo.
3. **Encerrando a Call:** Acabou a reunião? Pressione **`Ctrl + S`**. 
   - O AtaFlow interrompe a gravação.
   - Salva a transcrição bruta na pasta `./transcricoes/`.
   - Aciona a IA (Ollama ou Gemini) para ler a conversa e cuspir uma **Ata Profissional em Markdown**.
   - Você é notificado e o app encerra sozinho.

### ⌨️ Atalhos da Interface
- **`Ctrl+L`**: Limpa a tela de transcrição (não apaga os dados salvos).
- **`F1`**: Abre o menu de Ajuda interativo.
- **`Ctrl+S` ou `Ctrl+C`**: Salva e encerra.

---

## 🏗️ Para Desenvolvedores
Quer contribuir? O AtaFlow possui uma arquitetura altamente modular e desacoplada baseada no ecossistema `Agy`. 

Consulte o arquivo [CONTRIBUTING.md](CONTRIBUTING.md) para explorar a arquitetura, entender o *Strategy Pattern* utilizado no processamento de voz (`agy_voice`), o design da TUI (`agy_tui`), e como rodar nossa suíte de testes automáticos.