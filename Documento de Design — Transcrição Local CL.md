**Documento de Design --- Transcrição Local CLI**

**1. Visão geral**

Ferramenta de linha de comando para captura e transcrição local de reuniões no Windows 10/11.

O sistema deverá capturar simultaneamente:

• áudio do microfone;

• áudio de saída do sistema por WASAPI loopback.

A transcrição será realizada localmente com faster-whisper, priorizando a GPU NVIDIA GTX 1650 quando CUDA estiver disponível. Na ausência de CUDA, o sistema deverá utilizar fallback para CPU.

A primeira versão terá escopo estritamente offline. Nenhum áudio, texto ou metadado será enviado a serviços externos. O resumo local será considerado para a versão seguinte, após a validação do núcleo de captura e transcrição.

A interface inicial será exclusivamente CLI. A prioridade é obter um fluxo simples, confiável e recuperável antes de adicionar recursos de interface gráfica ou integrações externas.

**2. Objetivos**

**Objetivos da v0**

• Capturar microfone e áudio do sistema.

• Misturar os sinais em um fluxo mono.

• Transcrever em português brasileiro.

• Processar o áudio de forma incremental.

• Exibir o texto no terminal durante a reunião.

• Manter timestamps nos segmentos transcritos.

• Utilizar chunks padrão de 10 segundos com sobreposição de 2 segundos.

• Permitir configuração de latência e duração dos chunks.

• Acompanhar a reunião com atraso operacional desejado de até 30 segundos.

• Salvar o progresso automaticamente.

• Encerrar com segurança mediante Ctrl+C.

• Funcionar com GPU ou CPU.

**Objetivos da v0.1**

• Gerar resumo local após a transcrição.

• Produzir saída estruturada em Markdown.

• Preservar a transcrição caso o resumo falhe.

• Melhorar parâmetros de CLI e mensagens de erro.

• Permitir seleção específica de dispositivos de áudio.

**3. Não objetivos**

Permanecem fora do escopo atual:

• envio de áudio ou texto para serviços externos;

• resumo externo ou integração com APIs de nuvem;

• diarização e identificação automática de participantes;

• interface gráfica desktop ou web;

• integração com agenda ou calendário;

• telemetria, analytics ou tracking;

• processamento avançado de ruído;

• suporte obrigatório a múltiplos idiomas;

• gravação permanente do áudio bruto;

• VAD baseado em pausas naturais com Silero.

**4. Ambiente e restrições**

|                     |                                    |
|:--------------------|:-----------------------------------|
| Item                | Definição                          |
| Sistema operacional | Windows 10/11                      |
| Runtime             | Python 3.10 ou superior            |
| Interface           | CLI                                |
| GPU principal       | NVIDIA GeForce GTX 1650, 4 GB VRAM |
| Modelo padrão       | faster-whisper small               |
| Idioma inicial      | Português (pt)                     |
| Operação            | 100% offline                       |
| Pasta padrão        | ./transcricoes/                    |
| Codificação         | UTF-8                              |

O modelo small será o padrão por oferecer equilíbrio entre qualidade e consumo de memória. Modelos maiores poderão ser avaliados posteriormente, mas não serão tratados como requisito da primeira versão.

**5. Requisitos não funcionais**

**Performance**

• O sistema deverá processar áudio continuamente sem interromper a captura.

• A atualização textual esperada será aproximadamente a cada 5--10 segundos em condições normais.

• O atraso operacional desejado será configurável, com limite de referência de até 30 segundos.

• A latência real dependerá do modelo, backend, qualidade do áudio e carga da GPU.

• O sistema deverá indicar quando a transcrição estiver atrasada.

• A fila de chunks terá capacidade máxima para impedir crescimento indefinido.

**Confiabilidade**

• O texto já processado deverá ser salvo mesmo em caso de falha.

• Ctrl+C deverá iniciar encerramento controlado.

• As fatias pendentes deverão ser processadas quando possível.

• Threads deverão ser finalizadas com timeout de 5 segundos.

• Falhas em uma fatia não deverão apagar os resultados anteriores.

• Nenhum áudio deverá ser descartado silenciosamente.

**Privacidade**

• Todo o processamento da v0 ocorrerá localmente.

• Não haverá telemetria nem registro remoto.

• Logs não deverão conter transcrições completas ou credenciais.

• O usuário deverá informar os participantes e obter os consentimentos aplicáveis antes da gravação.

• O áudio bruto será temporário e não será salvo por padrão.

**Manutenibilidade**

• Cada módulo deverá possuir responsabilidade clara.

• Funções públicas deverão utilizar type hints e docstrings.

• Dependências de captura e transcrição deverão ser abstraídas.

• O núcleo deverá ser testável sem depender sempre de dispositivos reais.

• O código deverá seguir ruff format e ruff check.

**6. Arquitetura**

A arquitetura utilizará o padrão producer-consumer:

> Thread Producer
>
> ↓
>
> Fila de chunks de áudio
>
> ↓
>
> Thread Consumer
>
> ↓
>
> Fila de segmentos transcritos
>
> ↓
>
> Thread principal
>
> ↓
>
> Exibição e persistência

**Producer**

Responsável por:

• iniciar a captura;

• ler microfone e loopback;

• aplicar ganho individual;

• converter os sinais para o formato interno;

• misturar os canais;

• gerar chunks;

• aplicar sobreposição;

• inserir os chunks na fila.

**Consumer**

Responsável por:

• carregar e manter o modelo;

• processar os chunks;

• utilizar CUDA ou CPU;

• aplicar o idioma configurado;

• preservar timestamps;

• eliminar duplicações entre chunks;

• enviar segmentos processados para a fila de saída.

**Thread principal**

Responsável por:

• interpretar argumentos;

• exibir o status;

• mostrar a transcrição incremental;

• acumular segmentos;

• salvar o progresso;

• tratar Ctrl+C;

• coordenar o encerramento.

**7. Módulos previstos**

> transcriber-local/
>
> ├── main.py
>
> ├── audio_capture.py
>
> ├── transcriber.py
>
> ├── session_manager.py
>
> ├── requirements.txt
>
> ├── README.md
>
> ├── transcricoes/
>
> └── tests/

**main.py**

Ponto de entrada da aplicação. Deverá interpretar a configuração, iniciar a sessão e exibir erros de alto nível em português.

**audio_capture.py**

Conterá o protocolo de captura e a implementação baseada em PyAudioWPatch.

**transcriber.py**

Conterá o carregamento do modelo, seleção do backend, transcrição e deduplicação.

**session_manager.py**

Orquestrará threads, filas, estados da sessão, persistência e encerramento.

**8. Captura e normalização de áudio**

O áudio interno deverá utilizar:

|                    |               |
|:-------------------|:--------------|
| Parâmetro          | Valor         |
| Taxa de amostragem | 16.000 Hz     |
| Canais             | Mono          |
| Tipo               | numpy.float32 |
| Faixa esperada     | -1.0 a 1.0    |

O producer deverá:

1\. capturar as fontes disponíveis;

2\. converter cada sinal para mono;

3\. reamostrar para 16 kHz quando necessário;

4\. aplicar mic_volume e system_volume;

5\. misturar os sinais;

6\. normalizar o pico quando ultrapassar 1.0;

7\. armazenar o áudio no buffer de chunking.

Na v0, o loopback capturará todo o áudio de saída do sistema. A seleção de um dispositivo específico ficará para a v0.1. O usuário será responsável por silenciar fontes indesejadas.

**9. Chunking e latência**

A configuração padrão será:

• duração do chunk: 10 segundos;

• sobreposição: 2 segundos;

• fila máxima: 10 chunks.

A sobreposição será preservada entre chunks consecutivos para reduzir cortes de palavras. O conteúdo repetido será removido na etapa de consolidação.

A duração do chunk e a sobreposição deverão ser configuráveis. O atraso de até 30 segundos será uma meta operacional, não uma garantia absoluta. O sistema deverá exibir:

• número de chunks pendentes;

• atraso aproximado;

• estado da fila;

• backend em uso;

• indicação de processamento atrasado.

A configuração poderá utilizar parâmetros diretos de CLI. Presets de latência poderão ser adicionados posteriormente, mas não são necessários para validar o núcleo.

**10. Transcrição**

O modelo padrão será faster-whisper small, com idioma fixo em português na v0.

**Backend CUDA**

Quando disponível:

• dispositivo: cuda;

• tipo de computação: float16.

**Backend CPU**

Quando CUDA não estiver disponível ou falhar:

• dispositivo: cpu;

• tipo de computação: int8.

O fallback deverá ser informado no terminal. A aplicação não deverá presumir que CUDA está corretamente configurado apenas porque existe uma GPU NVIDIA.

O filtro de silêncio nativo do faster-whisper poderá ser utilizado conforme a configuração validada, mas o Silero VAD baseado em pausas naturais permanecerá fora da v0.

**11. Timestamps e deduplicação**

Cada segmento transcrito deverá manter, sempre que possível:

• tempo inicial;

• tempo final;

• texto;

• ordem de origem.

Os timestamps estarão presentes desde a v0, contrariando a classificação anterior do documento de referência que os colocava na v0.1.

A deduplicação deverá ocorrer na fronteira entre chunks. O processo deverá:

1\. comparar o final do texto anterior com o início do texto atual;

2\. remover repetições exatas quando identificadas;

3\. utilizar comparação aproximada apenas como fallback;

4\. preservar o texto quando houver incerteza;

5\. evitar que a deduplicação remova conteúdo legítimo.

A prioridade será preservar informação, ainda que alguma repetição permaneça, em vez de apagar palavras potencialmente válidas.

**12. Persistência**

A transcrição será salva incrementalmente em arquivo UTF-8 na pasta ./transcricoes/.

Formato de nome padrão:

> YYYY-MM-DD_HHhMM-reuniao.txt

O arquivo deverá conter segmentos em ordem temporal, preferencialmente no formato:

> \[00:00:00 - 00:00:10\] Texto transcrito.

O salvamento deverá ocorrer:

• após cada segmento confirmado;

• durante o encerramento;

• antes de finalizar a sessão;

• após falhas recuperáveis.

A aplicação deverá utilizar escrita segura para reduzir o risco de corromper o arquivo durante uma interrupção. O resultado já salvo deverá permanecer utilizável mesmo que a sessão não seja concluída.

**13. Ciclo de vida da sessão**

**Inicialização**

• validar a configuração;

• verificar modelo e dependências;

• detectar CUDA;

• selecionar backend;

• verificar dispositivos de áudio;

• preparar o arquivo de saída;

• solicitar confirmação antes da captura.

**Execução**

• iniciar producer e consumer;

• capturar e processar chunks;

• exibir transcrição;

• persistir segmentos;

• monitorar fila e latência.

**Encerramento normal**

• interromper a produção de novos chunks;

• finalizar a captura;

• processar chunks pendentes;

• consolidar os segmentos;

• salvar o arquivo final;

• encerrar threads;

• informar o status.

**Encerramento por Ctrl+C**

• capturar a interrupção;

• sinalizar o evento de encerramento;

• impedir novos chunks;

• processar pendências dentro do limite configurado;

• salvar o conteúdo disponível;

• finalizar threads com timeout;

• informar se houve dados não processados.

**14. Tratamento de falhas**

**CUDA indisponível**

A aplicação deverá alternar para CPU e informar a mudança. Se a CPU não conseguir acompanhar a captura, a fila e o atraso deverão ser exibidos ao usuário.

**Falha na captura**

A sessão deverá interromper a leitura, preservar a transcrição já salva e exibir uma mensagem clara. O sistema não deverá continuar como se a captura estivesse ativa.

**Falha na transcrição de um chunk**

O erro deverá ser registrado sem expor conteúdo sensível. A aplicação deverá:

• preservar os chunks anteriores;

• informar o timestamp aproximado afetado;

• continuar quando possível;

• marcar a lacuna para revisão.

**Fila cheia**

A aplicação deverá informar que o processamento está atrasado. Não deverá descartar áudio silenciosamente. O comportamento de descarte controlado, caso seja necessário em versões futuras, exigirá decisão específica.

**Falha de persistência**

A sessão deverá alertar o usuário imediatamente. O sistema deverá tentar preservar dados em arquivo temporário local e não apagar arquivos existentes.

**15. Resumo local na v0.1**

O resumo automático não fará parte do MVP. Na v0.1, poderá ser adicionado um modelo executado localmente após a conclusão da transcrição.

O resumo deverá:

• receber apenas a transcrição consolidada;

• funcionar sem conexão externa;

• produzir Markdown;

• preservar a transcrição original;

• indicar incertezas;

• não inventar decisões, tarefas ou responsáveis;

• deixar informações ausentes como não identificadas.

Estrutura prevista:

1\. Resumo geral;

2\. Principais pontos;

3\. Decisões;

4\. Tarefas e próximos passos;

5\. Responsáveis explicitamente mencionados;

6\. Questões pendentes;

7\. Observações e incertezas.

A inclusão na v0.1 dependerá da validação de desempenho e consumo de memória na GTX 1650.

**16. Testes**

**Testes unitários**

Deverão cobrir:

• conversão de canais;

• reamostragem;

• aplicação de ganho;

• normalização;

• criação de chunks;

• sobreposição;

• deduplicação;

• ordenação de timestamps;

• leitura de configuração;

• persistência incremental;

• montagem do arquivo final;

• tratamento de filas;

• encerramento.

**Testes de integração**

Deverão verificar:

• producer alimentando a fila;

• consumer processando chunks simulados;

• fallback CUDA para CPU;

• interrupção por Ctrl+C;

• recuperação após falha;

• processamento das pendências;

• persistência durante a sessão;

• encerramento com timeout;

• execução sem dispositivos reais por meio de backends simulados.

A captura real via WASAPI deverá ser validada manualmente no Windows com os dispositivos disponíveis.

**17. Critérios de aceitação da v0**

A v0 será considerada funcional quando:

• capturar microfone e loopback;

• misturar os sinais corretamente;

• transcrever em português;

• exibir texto incrementalmente;

• incluir timestamps;

• utilizar chunks de 10 segundos com sobreposição de 2 segundos;

• permitir configuração dos principais parâmetros;

• acompanhar a reunião em condições normais;

• manter atraso desejado de até 30 segundos;

• utilizar GPU quando disponível;

• fazer fallback para CPU;

• salvar progresso continuamente;

• encerrar com segurança via Ctrl+C;

• preservar dados após uma falha;

• operar sem conexão externa;

• não gerar resumo automático.

**18. Critérios de aceitação da v0.1**

A v0.1 deverá, adicionalmente:

• gerar resumo local;

• salvar o resumo em Markdown;

• manter a transcrição original separada;

• continuar funcionando quando o resumo falhar;

• sinalizar conteúdo incerto;

• não inventar responsáveis, decisões ou tarefas.

**19. Premissas**

1\. As reuniões terão qualidade de áudio semelhante a Meet, Teams ou Zoom.

2\. O áudio não exigirá redução avançada de ruído na v0.

3\. O loopback capturará todo o áudio do sistema.

4\. O usuário silenciará fontes não relacionadas à reunião.

5\. CUDA poderá não estar configurado.

6\. O modelo small será suficiente para qualidade aceitável em português brasileiro.

7\. O modelo medium não será considerado adequado para uso GPU na GTX 1650.

8\. O usuário terá familiaridade básica com Python, pip e ambientes virtuais.

9\. A transcrição não precisará aparecer palavra por palavra.

10\. O processamento local será suficiente para o requisito de privacidade.

11\. O resumo local poderá exigir modelo e recursos adicionais.

12\. Não haverá identificação automática de quem falou.

13\. A proteção dos arquivos dependerá inicialmente das permissões e criptografia do Windows.

**20. Decision log consolidado**

|  |  |  |  |
|---:|:---|:---|:---|
| Nº | Decisão | Alternativas consideradas | Justificativa |
| 1 | Operação 100% offline na v0 | Usar provedor externo | Privacidade e simplicidade |
| 2 | CLI como interface inicial | GUI desktop ou web | Validar o núcleo antes da interface |
| 3 | Capturar loopback completo na v0 | Selecionar dispositivos específicos | Menor complexidade inicial |
| 4 | Usar PyAudioWPatch com abstração | Usar soundcard diretamente | Compatibilidade com WASAPI e possibilidade de troca |
| 5 | Usar producer-consumer com threads | Processamento sequencial | Evitar bloqueio da captura |
| 6 | Usar chunks de 10 s com overlap de 2 s | Chunks sem overlap ou VAD imediato | Equilíbrio entre contexto e latência |
| 7 | Permitir configuração de chunks e latência | Valores totalmente fixos | Adaptar o comportamento ao hardware |
| 8 | Meta operacional de até 30 s | Garantia rígida de latência | Desempenho depende do ambiente |
| 9 | Fallback automático para CPU | Exigir CUDA | Melhor compatibilidade |
| 10 | Modelo small como padrão | Modelo maior | Compatibilidade com 4 GB de VRAM |
| 11 | Timestamps desde a v0 | Adiar para a v0.1 | Facilitar revisão e validação |
| 12 | Persistência incremental | Salvar apenas no encerramento | Evitar perda de dados |
| 13 | Silero VAD fora da v0 | Adotá-lo imediatamente | Reduzir complexidade inicial |
| 14 | Resumo fora da v0 | Incluir no MVP | Manter o MVP estritamente offline e focado |
| 15 | Resumo local na v0.1 | Resumo externo | Preservar privacidade e evitar dependência de nuvem |
| 16 | Sem diarização | Identificar participantes | Recurso complexo e não essencial |
| 17 | Nenhuma telemetria | Analytics anônimo | Minimizar coleta de dados |
| 18 | Mensagens em PT-BR e código em inglês | Padronizar tudo em um idioma | Equilibrar usabilidade e manutenção |
| 19 | Estrutura plana de módulos | Subpacotes desde o início | Evitar complexidade prematura |
| 20 | Preservar dados em falhas | Encerrar descartando pendências | Priorizar confiabilidade |

**21. Escopo por versão**

**v0 --- MVP**

• Captura de microfone;

• Captura de loopback;

• Controle de ganho;

• Chunks configuráveis;

• Sobreposição;

• Transcrição local;

• Modelo small;

• Português;

• CUDA com fallback para CPU;

• Timestamps;

• Feedback incremental;

• Salvamento automático;

• Encerramento seguro;

• Operação offline.

**v0.1**

• Resumo local;

• Saída Markdown;

• Parâmetros ampliados via CLI;

• Seleção de dispositivo;

• Mensagens de erro aprimoradas;

• Aviso para modelos com alto consumo de VRAM.

**v0.2 ou posterior**

• Silero VAD;

• Salvamento opcional do áudio bruto;

• Múltiplos idiomas;

• Configuração YAML ou JSON;

• Formatos de saída adicionais;

• Melhorias avançadas de pré-processamento.

**Sem previsão**

• Resumo externo;

• Diarização;

• GUI;

• Integração com calendário;

• Telemetria;

• Dependência de nuvem.
