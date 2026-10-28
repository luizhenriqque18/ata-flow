# 🎙️ AtaFlow (v2.1.0)
**Transcrição local de reuniões e geração de atas com Gemini.**

O **AtaFlow** é uma ferramenta de linha de comando com uma **Interface Gráfica no Terminal (TUI)** incrivelmente fluida, desenvolvida em Python. Ele escuta simultaneamente o seu microfone e o áudio do sistema (colegas de trabalho, vídeos, apresentações) e gera uma transcrição em tempo real, transcrevendo localmente na sua máquina. A geração de atas usa o Gemini e envia a transcrição textual ao Google.

Diga adeus ao trabalho manual de anotar tudo durante as calls!

---

## 🚀 Principais Funcionalidades

- **🖥️ Interface Visual de Terminal (TUI):** Navegue com facilidade. Esqueça a configuração manual de índices de áudio — basta abrir o app e selecionar seus dispositivos com as setas do teclado.
- **🗣️ Diarização Automática:** O sistema identifica e rotula automaticamente quem está falando com as tags `[Você]`, `[Outros]` ou `[Você + Outros]`.
- **🧠 Resumos Inteligentes com IA:** Ao final da reunião, gera uma ata profissional e estruturada em Markdown, destacando pontos principais e decisões. Usa o **Gemini**, com catálogo, favoritos e escolha de modelo padrão pela interface.
- **🔒 Privacidade e Performance:** Transcrição feita localmente com o motor **Faster-Whisper** (com suporte à aceleração CUDA para placas NVIDIA). O áudio é processado localmente; a transcrição textual é enviada ao Gemini quando você solicita uma ata.
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
*(No arquivo `.env`, você pode definir o idioma padrão, configurar a chave Gemini e o modelo inicial, etc).*

### 3. Habilitar Aceleração (Apenas Placas NVIDIA)
Para processar o áudio com a sua placa de vídeo (como uma RTX ou GTX), instale as bibliotecas NVIDIA essenciais:

```powershell
uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

### 4. Configurar o Gemini

Defina `GEMINI_API_KEY` no `.env`. O Gemini é o único provedor de atas suportado.
As antigas variáveis `LLM_PROVIDER` e `OLLAMA_DEFAULT_MODEL` não são mais utilizadas.

Antes de configurar seus favoritos, `GEMINI_DEFAULT_MODEL` define a sugestão inicial.
Depois, o padrão salvo na interface tem prioridade.

### 5. Gerenciar modelos

Abra **Gerenciar modelos** no painel inicial ou na janela de geração de atas.

- À esquerda: catálogo completo retornado pelo Gemini, com busca, filtro de versão e de status.
- À direita: seus favoritos; selecione um e clique **Definir padrão** para marcá-lo com ★.
- Modelos especializados ou sem suporte à geração de texto aparecem como incompatíveis.
- **Testar selecionado** verifica um modelo; **Testar todos** verifica todos os compatíveis,
  independentemente dos filtros. Os testes usam texto sintético e podem consumir cota da API.
- Veja o último resultado, código HTTP, horário em UTC e duração nos detalhes do modelo.
- Os testes são sequenciais, podem ser interrompidos e param ao receber HTTP 429.
- Clique **Salvar** para manter favoritos, padrão, catálogo e resultados dos testes.
  **Cancelar** descarta as alterações feitas nessa tela.

As preferências ficam em `model_preferences.json`, ignorado pelo Git, sem chaves de API.
A listagem não executa testes de geração automaticamente. Um resultado de disponibilidade
reflete somente o último teste; não garante a próxima geração nem avalia a qualidade da ata.

Em **Modelo escolhido**, seus favoritos são exibidos com o padrão pré-selecionado.
Escolher outro modelo para uma ata não muda o padrão salvo. Se o padrão desaparecer
do catálogo, escolha outro explicitamente ou atualize suas preferências.

---

## 💻 Como Usar no Dia a Dia

### Resumos em outros chats (MCP)

Abra **Servidor MCP** no painel inicial para ativar/desativar o acesso local aos
resumos, escolher a pasta compartilhada e ajustar os limites de leitura.
Use stdio localmente ou ative **Acesso pela rede (HTTP)** para outro computador,
com IP, porta e token configuráveis. A tela gera a configuração de conexão para
o Codex e outros clientes. O acesso começa desativado e é somente de leitura. Veja o
[guia de conexão e uso](docs/mcp.md) para usar atas como contexto ou preparar e-mails.

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
   - Abre a escolha do modelo Gemini e, após confirmar, aciona a IA para ler a conversa e cuspir uma **Ata Profissional em Markdown**.
   - Você é notificado e retorna ao painel, onde pode abrir a ata ou gerar resumos pendentes.

### ⌨️ Atalhos da Interface
- **`Ctrl+L`**: Limpa a tela de transcrição (não apaga os dados salvos).
- **`F1`**: Abre o menu de Ajuda interativo.
- **`Ctrl+S` ou `Ctrl+C`**: Salva e encerra.

---

## 🏗️ Para Desenvolvedores
Quer contribuir? O AtaFlow possui uma arquitetura altamente modular e desacoplada baseada no ecossistema `Agy`. 

Consulte o arquivo [CONTRIBUTING.md](CONTRIBUTING.md) para explorar a arquitetura, entender o *Strategy Pattern* utilizado no processamento de voz (`agy_voice`), o design da TUI (`agy_tui`), e como rodar nossa suíte de testes automáticos.
