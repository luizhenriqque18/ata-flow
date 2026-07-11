# Skills Recomendadas para o Projeto: Transcrição Local CLI

Este documento lista as skills da IA que estão instaladas e devem ser consideradas/ativadas para auxiliar no desenvolvimento da ferramenta de linha de comando para captura e transcrição local de reuniões no Windows 10/11.

## 1. Desenvolvimento Python & CLI

* **`python-pro`**: Ideal para estruturar o código do projeto com as melhores práticas (Python 3.12+), tipagem avançada e, principalmente, **concorrência/asyncio**. Fundamental para capturar duas fontes de áudio de forma simultânea (Microfone e WASAPI) sem bloquear a interface de linha de comando ou a engine de transcrição.
* **`ai-native-cli`**: Ajuda a desenhar a interface de linha de comando (CLI) da ferramenta de forma moderna, intuitiva e focada em IA.
* **`windows-shell-reliability`** e **`powershell-windows`**: Como a ferramenta é focada no Windows 10/11, essas skills garantirão que caminhos de arquivos, codificações de texto e a execução geral no terminal do Windows ocorram sem bugs.

## 2. Captura e Processamento de Áudio

* **`audio-transcriber`**: Contém padrões para transformar gravações de áudio em documentos (como Markdown) com resumos inteligentes. Muito útil para a etapa final, quando o áudio capturado precisar ser pós-processado, formatado e salvo.
* **`voice-agents`** e **`voice-ai-development`**: Contêm conhecimentos valiosos e padrões de arquitetura sobre manipulação de fluxos contínuos de áudio (streaming) em tempo real, algo essencial ao processar chunks do microfone e do WASAPI loopback ao mesmo tempo.

## 3. Transcrição com IA Local

* **`local-llm-expert`**: Ajuda a configurar e rodar a transcrição de forma estritamente local (por exemplo, usando modelos como o Whisper rodando via `whisper.cpp`, `faster-whisper` ou outras ferramentas offline), otimizando o uso da CPU e GPU da máquina.
* **`hugging-face-cli`** / **`transformers-js`**: Úteis caso seja necessário baixar, gerenciar ou interagir programaticamente com modelos de áudio open-source hospedados no Hugging Face.
