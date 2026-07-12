# Transcritor Local CLI

O Transcritor Local é uma ferramenta CLI (Linha de Comando) desenvolvida em Python que escuta simultaneamente o seu microfone e o áudio interno do sistema (reuniões, vídeos, jogos) e gera uma transcrição em tempo real, operando **100% offline** na sua máquina.

## Funcionalidades
- **Captura Simultânea:** Usa `PyAudioWPatch` (API WASAPI Loopback do Windows) para ouvir o sistema e o microfone ao mesmo tempo.
- **Processamento Offline:** Utiliza o modelo `faster-whisper` (OpenAI Whisper otimizado) acelerado por placa de vídeo (CUDA).
- **Tratamento de Áudio Robusto:** Realiza o *downmix* (Estéreo -> Mono) e *resample* (ex: 48kHz -> 16kHz) do áudio nativo em tempo real para evitar distorções (alucinações da IA).
- **Interface Contínua:** Renderiza o histórico de falas formatado no terminal com a biblioteca `rich`.
- **Exportação:** Salva as transcrições automaticamente em arquivos `.txt` com base na data da sessão.

## 📦 Instalação (Primeira Vez)

Siga os passos abaixo após clonar este repositório para a sua máquina Windows:

### 1. Preparar o Ambiente
Certifique-se de ter o Python 3.9+ instalado. Recomenda-se criar um ambiente virtual na pasta do projeto:
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar Dependências do Projeto
```bash
pip install -r requirements.txt
```

### 3. Habilitar Suporte a Placa de Vídeo (Obrigatório para NVIDIA)
Para que o `faster-whisper` reconheça sua placa de vídeo (ex: GTX 1650) corretamente no Windows e use aceleração de hardware (CUDA), instale as bibliotecas do cuBLAS diretamente via `pip`:
```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
*(O script já foi configurado para injetar essas bibliotecas dinamicamente no PATH do Windows durante a execução, você não precisa configurar variáveis de ambiente).*

## 🚀 Como Usar no Dia a Dia

Para rodar o assistente de transcrição, basta abrir o seu terminal favorito, ativar o ambiente virtual e iniciar o arquivo `main.py`:

```bash
python main.py
```

### Argumentos Opcionais Avançados
Você pode alterar o comportamento da IA passando parâmetros na linha de comando:

- `--model` (Tamanho do modelo. Padrão: `small`):
  `python main.py --model base`
- `--chunk` (Tamanho da gravação em segundos enviada pra IA por vez. Padrão: `10.0`):
  `python main.py --chunk 5.0`
- `--overlap` (Sobreposição de segurança entre um chunk e outro para não cortar palavras pela metade. Padrão: `2.0`):
  `python main.py --overlap 1.0`

### Encerrando e Salvando a Sessão
Quando a reunião acabar, pressione **`Ctrl + C`** no terminal.
O programa interceptará o comando e fará um encerramento seguro (*Graceful Shutdown*), aguardando o processamento do último bloco de áudio que estiver na fila.

Todas as transcrições da sessão ficam salvas na pasta `./transcricoes/` com o nome exato da data e hora da reunião.
