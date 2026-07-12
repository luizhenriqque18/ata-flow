# Transcritor Local CLI (v0.1)

O Transcritor Local é uma ferramenta CLI (Linha de Comando) desenvolvida em Python que escuta simultaneamente o seu microfone e o áudio interno do sistema (reuniões, vídeos, jogos) e gera uma transcrição em tempo real, operando **100% offline** na sua máquina.

Na versão 0.1, a aplicação ganhou **Diarização Simples** (identifica se é você ou outras pessoas falando) e **Geração Automática de Resumos em Markdown** usando Inteligência Artificial local (Ollama).

## ✨ Funcionalidades
- **Captura Simultânea:** Usa a API WASAPI Loopback do Windows para ouvir o sistema e o microfone ao mesmo tempo.
- **Diarização (Novo):** Rotula automaticamente cada linha da transcrição com `[Você]`, `[Outros]` ou `[Você + Outros]`.
- **Resumo Inteligente (Novo):** Gera uma ata profissional em Markdown com os pontos principais e decisões assim que a reunião acaba.
- **Processamento Offline:** Utiliza o modelo `faster-whisper` (acelerado por CUDA) para a transcrição e o `Ollama` para o resumo. Privacidade absoluta.
- **Tratamento de Áudio Robusto:** Realiza o *downmix* (Estéreo -> Mono) e *resample* (ex: 48kHz -> 16kHz) nativo para evitar alucinações da IA.
- **Seleção de Dispositivos (Novo):** Permite listar e escolher exatamente qual microfone e qual saída de áudio capturar.

---

## 📦 Instalação (Primeira Vez)

Siga os passos abaixo após clonar este repositório para a sua máquina Windows:

### 1. Preparar o Ambiente Python
Certifique-se de ter o Python 3.9+ instalado. Recomenda-se criar um ambiente virtual na pasta do projeto:
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar Dependências do Projeto
```bash
pip install -r requirements.txt
```

### 3. Habilitar Placa de Vídeo (Obrigatório para NVIDIA)
Para que a transcrição reconheça sua GPU (ex: GTX 1650) corretamente no Windows e use aceleração de hardware, instale as bibliotecas do cuBLAS via `pip`:
```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
*(O script injeta essas bibliotecas dinamicamente no PATH, você não precisa configurar variáveis de ambiente).*

### 4. Instalar o Motor de Resumos (Opcional, mas recomendado)
Para que o sistema consiga gerar atas automáticas após as reuniões, ele possui suporte nativo a dois provedores de Inteligência Artificial:

**Opção A: Ollama (100% Offline, Maior Privacidade)**
1. Baixe e instale o [Ollama para Windows](https://ollama.com/).
2. Abra um terminal comum e baixe o modelo leve que utilizamos como padrão:
```bash
ollama run llama3.2:1b
```

**Opção B: Google Gemini (Online, Maior Qualidade)**
Se você possui uma chave de API do Google Gemini, você pode configurá-la no sistema para gerar resumos mais potentes:
```bash
python main.py --set-gemini-key "SUA_CHAVE_AQUI"
```
*(A chave será salva de forma persistente em um arquivo `config.json` local).*

---

## 🚀 Como Usar no Dia a Dia

Para rodar o assistente de transcrição, abra o seu terminal na pasta do projeto, ative o ambiente virtual e inicie o `main.py`.

### Passo A: Identificar seus dispositivos de áudio
Antes da primeira execução, verifique quais são os "índices" (IDs) do seu fone e microfone:
```bash
python main.py --list-devices
```
Isso imprimirá duas tabelas (uma de Microfones e outra de Loopbacks do sistema). Anote os números da coluna "Índice" que você deseja gravar.

### Passo B: Iniciar a Reunião
Inicie a transcrição passando os índices que você anotou. (Se você não passar os índices, ele tentará usar os dispositivos padrão do Windows):
```bash
python main.py --mic-index 1 --sys-index 28
```

### Salvar Preferências de Inteligência Artificial
Se você quiser deixar a sua escolha salva, em vez de passar os argumentos `--provider` ou `--llm` toda vez, você pode rodar os seguintes comandos para salvar sua preferência (ficam gravadas no `config.json`):

```bash
# Define o Gemini como motor padrão
python main.py --set-default-provider gemini

# Verifica a lista de LLMs e define um modelo padrão
python main.py --provider gemini --list-llms
python main.py --provider gemini --set-default-llm gemini-2.5-pro
```

### Argumentos Opcionais Avançados
- `--provider` (Qual motor de Inteligência Artificial usar para o resumo: `ollama` ou `gemini`. Padrão salvo no `config.json`).
- `--list-llms` (Lista todos os modelos LLM disponíveis baseados no provedor atual e sai).
- `--llm` (O modelo de inteligência. Padrão salvo no `config.json` para cada provedor):
  `python main.py --llm phi3.5:latest`
- `--model` (Tamanho do modelo de transcrição Whisper. Padrão: `small`):
  `python main.py --model base` *(Aviso: Modelos como `medium` ou superiores exigem mais de 4GB de VRAM).*
- `--chunk` (Tamanho da gravação em segundos enviada pra IA por vez. Padrão: `10.0`).
- `--overlap` (Sobreposição de segurança para não cortar palavras pela metade. Padrão: `2.0`).

### 🛑 Encerrando e Salvando a Sessão
Quando a reunião acabar, pressione **`Ctrl + C`** no terminal.
O programa fará o seguinte:
1. Aguardará os últimos segundos de áudio serem transcritos.
2. Salvará a transcrição bruta (com as tags `[Você]`/`[Outros]`) na pasta `./transcricoes/` como um arquivo `.txt`.
3. **[Novo]** Se o Ollama estiver instalado, o programa lerá todo o `.txt` gerado e invocará a IA para gerar um resumo profissional, salvando-o como um arquivo `.md` na mesma pasta!
