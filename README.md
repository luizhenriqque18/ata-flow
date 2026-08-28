# AtaFlow CLI (v0.2)

O AtaFlow Ã© uma ferramenta de linha de comando com uma **Interface GrÃ¡fica no Terminal (TUI)** desenvolvida em Python. Ele escuta simultaneamente o seu microfone e o Ã¡udio interno do sistema (reuniÃµes, vÃ­deos, jogos) e gera uma transcriÃ§Ã£o em tempo real, operando **100% offline** na sua mÃ¡quina.

Na versÃ£o 0.2, a aplicaÃ§Ã£o ganhou uma reescrita arquitetural completa utilizando a plataforma gy, uma nova TUI interativa via **Textual**, e gestÃ£o moderna de ambiente com **uv** e **dotenv**.

## ðŸš€ Funcionalidades
- **TUI Interativa:** Interface visual diretamente no terminal. NÃ£o Ã© mais necessÃ¡rio procurar Ã­ndices de dispositivos manualmente â€” basta abrir o app e selecionar com as setas do teclado.
- **DiarizaÃ§Ã£o Simples:** Rotula automaticamente cada linha da transcriÃ§Ã£o com [VocÃª], [Outros] ou [VocÃª + Outros].
- **Resumo Inteligente:** Gera uma ata profissional em Markdown com os pontos principais e decisÃµes assim que a reuniÃ£o acaba. Suporta IA local (Ollama) ou nuvem (Gemini).
- **Processamento Offline:** Utiliza o modelo aster-whisper (acelerado por CUDA) para a transcriÃ§Ã£o. Privacidade absoluta.
- **Tratamento de Ãudio Robusto:** Realiza o *downmix* (EstÃ©reo -> Mono) e *resample* (ex: 48kHz -> 16kHz) nativo para evitar alucinaÃ§Ãµes da IA.
- **Arquitetura Desacoplada:** CÃ³digo altamente modular utilizando gy_tui (biblioteca TUI reutilizÃ¡vel) e gy_voice (pacote com Strategy Pattern para integraÃ§Ãµes de voz).

---

## ðŸ› ï¸ InstalaÃ§Ã£o

Siga os passos abaixo apÃ³s clonar este repositÃ³rio para a sua mÃ¡quina Windows:

### 1. Preparar o Ambiente Python
Este projeto utiliza a ferramenta moderna [uv](https://docs.astral.sh/uv/) para gerenciar dependÃªncias e o ambiente virtual de forma ultrarrÃ¡pida. Certifique-se de ter o Python 3.12+ instalado.

`powershell
# Instale as dependÃªncias (o uv cria o .venv automaticamente)
uv sync
`

### 2. Configurar VariÃ¡veis de Ambiente
O projeto agora utiliza um arquivo .env para configuraÃ§Ãµes seguras (substituindo o antigo config.json).

1. Copie o template:
`powershell
copy .env.example .env
`
2. Edite o arquivo .env gerado e defina suas preferÃªncias (como a chave do Gemini, se for usÃ¡-lo, idioma e modelo do Whisper).

### 3. Habilitar Placa de VÃ­deo (ObrigatÃ³rio para NVIDIA)
Para que a transcriÃ§Ã£o reconheÃ§a sua GPU (ex: GTX 1650) corretamente no Windows e use aceleraÃ§Ã£o de hardware, instale as bibliotecas do cuBLAS via uv pip:
`powershell
uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
`
*(O script injeta essas bibliotecas dinamicamente no PATH, vocÃª nÃ£o precisa configurar variÃ¡veis de ambiente).*

### 4. Instalar o Motor de Resumos
O sistema gera atas automÃ¡ticas apÃ³s as reuniÃµes usando InteligÃªncia Artificial.

**OpÃ§Ã£o A: Ollama (100% Offline, Maior Privacidade)**
1. Baixe e instale o [Ollama para Windows](https://ollama.com/).
2. Abra um terminal comum e baixe o modelo padrÃ£o:
`powershell
ollama run llama3.2:1b
`
3. No seu .env, defina LLM_PROVIDER=ollama.

**OpÃ§Ã£o B: Google Gemini (Online, Maior Qualidade)**
Se vocÃª possui uma chave de API do Google Gemini, vocÃª pode configurÃ¡-la no .env:
`env
GEMINI_API_KEY=sua_chave_aqui
LLM_PROVIDER=gemini
`

---

## ðŸ’» Como Usar no Dia a Dia

A nova interface resolve os dispositivos para vocÃª! Basta executar:

`powershell
uv run python main.py
`

### O Fluxo:
1. **Setup Visual:** O app listarÃ¡ seus microfones e as saÃ­das de loopback do sistema. Use as **Setas**, **Tab** e **Enter** para escolher os dispositivos.
2. **TranscriÃ§Ã£o em Tempo Real:** A interface Textual serÃ¡ carregada exibindo o status do Ã¡udio, carregamento do modelo Whisper na GPU e o log de transcriÃ§Ã£o em tempo real.
3. **Comandos da Interface:**
   - **Ctrl+L**: Limpa o log visual.
   - **F1**: Exibe ajuda e comandos disponÃ­veis na interface.
   - **Ctrl+S ou Ctrl+C**: **Encerra a reuniÃ£o** e comeÃ§a a gerar o resumo.

### Modos RÃ¡pidos (CLI)
Se vocÃª quiser pular a tela de seleÃ§Ã£o inicial (Ãºtil para automaÃ§Ã£o), vocÃª ainda pode passar os Ã­ndices diretamente:
`powershell
# Lista os Ã­ndices no terminal e sai
uv run python main.py --list-devices

# Inicia direto com os Ã­ndices desejados
uv run python main.py --mic-index 1 --sys-index 31
`

### ðŸ Encerrando e Salvando a SessÃ£o
Quando a reuniÃ£o acabar, pressione **Ctrl + S** dentro da interface.
O programa farÃ¡ o seguinte:
1. PararÃ¡ a captura de Ã¡udio imediatamente.
2. SalvarÃ¡ a transcriÃ§Ã£o bruta (com as tags [VocÃª]/[Outros]) na pasta ./transcricoes/ como um arquivo .txt.
3. InvocarÃ¡ o seu LLM_PROVIDER escolhido (Ollama ou Gemini) para ler todo o arquivo e gerar um resumo profissional, salvando-o como .md na mesma pasta.
4. ExibirÃ¡ uma notificaÃ§Ã£o visual na tela quando o resumo estiver pronto e encerrarÃ¡.

---

## ðŸ—ï¸ Para Desenvolvedores (Arquitetura gy)
Consulte o arquivo [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes da arquitetura, como rodar a suÃ­te de testes (uv run pytest tests/) e como estender as bibliotecas nativas gy_tui (interface) e gy_voice (STT e IA).