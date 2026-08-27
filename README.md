# Transcritor Local CLI (v0.2)

O Transcritor Local é uma ferramenta de linha de comando com uma **Interface Gráfica no Terminal (TUI)** desenvolvida em Python. Ele escuta simultaneamente o seu microfone e o áudio interno do sistema (reuniões, vídeos, jogos) e gera uma transcrição em tempo real, operando **100% offline** na sua máquina.

Na versão 0.2, a aplicação ganhou uma reescrita arquitetural completa utilizando a plataforma gy, uma nova TUI interativa via **Textual**, e gestão moderna de ambiente com **uv** e **dotenv**.

## 🚀 Funcionalidades
- **TUI Interativa:** Interface visual diretamente no terminal. Não é mais necessário procurar índices de dispositivos manualmente — basta abrir o app e selecionar com as setas do teclado.
- **Diarização Simples:** Rotula automaticamente cada linha da transcrição com [Você], [Outros] ou [Você + Outros].
- **Resumo Inteligente:** Gera uma ata profissional em Markdown com os pontos principais e decisões assim que a reunião acaba. Suporta IA local (Ollama) ou nuvem (Gemini).
- **Processamento Offline:** Utiliza o modelo aster-whisper (acelerado por CUDA) para a transcrição. Privacidade absoluta.
- **Tratamento de Áudio Robusto:** Realiza o *downmix* (Estéreo -> Mono) e *resample* (ex: 48kHz -> 16kHz) nativo para evitar alucinações da IA.
- **Arquitetura Desacoplada:** Código altamente modular utilizando gy_tui (biblioteca TUI reutilizável) e gy_voice (pacote com Strategy Pattern para integrações de voz).

---

## 🛠️ Instalação

Siga os passos abaixo após clonar este repositório para a sua máquina Windows:

### 1. Preparar o Ambiente Python
Este projeto utiliza a ferramenta moderna [uv](https://docs.astral.sh/uv/) para gerenciar dependências e o ambiente virtual de forma ultrarrápida. Certifique-se de ter o Python 3.12+ instalado.

`powershell
# Instale as dependências (o uv cria o .venv automaticamente)
uv sync
`

### 2. Configurar Variáveis de Ambiente
O projeto agora utiliza um arquivo .env para configurações seguras (substituindo o antigo config.json).

1. Copie o template:
`powershell
copy .env.example .env
`
2. Edite o arquivo .env gerado e defina suas preferências (como a chave do Gemini, se for usá-lo, idioma e modelo do Whisper).

### 3. Habilitar Placa de Vídeo (Obrigatório para NVIDIA)
Para que a transcrição reconheça sua GPU (ex: GTX 1650) corretamente no Windows e use aceleração de hardware, instale as bibliotecas do cuBLAS via uv pip:
`powershell
uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
`
*(O script injeta essas bibliotecas dinamicamente no PATH, você não precisa configurar variáveis de ambiente).*

### 4. Instalar o Motor de Resumos
O sistema gera atas automáticas após as reuniões usando Inteligência Artificial.

**Opção A: Ollama (100% Offline, Maior Privacidade)**
1. Baixe e instale o [Ollama para Windows](https://ollama.com/).
2. Abra um terminal comum e baixe o modelo padrão:
`powershell
ollama run llama3.2:1b
`
3. No seu .env, defina LLM_PROVIDER=ollama.

**Opção B: Google Gemini (Online, Maior Qualidade)**
Se você possui uma chave de API do Google Gemini, você pode configurá-la no .env:
`env
GEMINI_API_KEY=sua_chave_aqui
LLM_PROVIDER=gemini
`

---

## 💻 Como Usar no Dia a Dia

A nova interface resolve os dispositivos para você! Basta executar:

`powershell
uv run python main.py
`

### O Fluxo:
1. **Setup Visual:** O app listará seus microfones e as saídas de loopback do sistema. Use as **Setas**, **Tab** e **Enter** para escolher os dispositivos.
2. **Transcrição em Tempo Real:** A interface Textual será carregada exibindo o status do áudio, carregamento do modelo Whisper na GPU e o log de transcrição em tempo real.
3. **Comandos da Interface:**
   - **Ctrl+L**: Limpa o log visual.
   - **F1**: Exibe ajuda e comandos disponíveis na interface.
   - **Ctrl+S ou Ctrl+C**: **Encerra a reunião** e começa a gerar o resumo.

### Modos Rápidos (CLI)
Se você quiser pular a tela de seleção inicial (útil para automação), você ainda pode passar os índices diretamente:
`powershell
# Lista os índices no terminal e sai
uv run python main.py --list-devices

# Inicia direto com os índices desejados
uv run python main.py --mic-index 1 --sys-index 31
`

### 🏁 Encerrando e Salvando a Sessão
Quando a reunião acabar, pressione **Ctrl + S** dentro da interface.
O programa fará o seguinte:
1. Parará a captura de áudio imediatamente.
2. Salvará a transcrição bruta (com as tags [Você]/[Outros]) na pasta ./transcricoes/ como um arquivo .txt.
3. Invocará o seu LLM_PROVIDER escolhido (Ollama ou Gemini) para ler todo o arquivo e gerar um resumo profissional, salvando-o como .md na mesma pasta.
4. Exibirá uma notificação visual na tela quando o resumo estiver pronto e encerrará.

---

## 🏗️ Para Desenvolvedores (Arquitetura gy)
Consulte o arquivo [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes da arquitetura, como rodar a suíte de testes (uv run pytest tests/) e como estender as bibliotecas nativas gy_tui (interface) e gy_voice (STT e IA).