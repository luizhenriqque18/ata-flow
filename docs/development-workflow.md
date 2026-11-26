# Protocolo de desenvolvimento e releases

Este documento registra as convenções acordadas para continuar o AtaFlow entre
sessões. O arquivo [AGENTS.md](../AGENTS.md) na raiz direciona os agentes para
estas regras. Uma instrução explícita do usuário na tarefa atual pode ajustar
o fluxo, por exemplo ao solicitar apenas planejamento ou proibir commits.

## Alterar e validar em etapas

1. Confira o estado do Git e leia a documentação relacionada ao escopo.
2. Explique a alteração proposta e divida melhorias independentes em etapas.
3. Implemente uma etapa, preservando os dados locais e as entradas compatíveis.
4. Valide o comportamento afetado, o lint e a formatação quando houver código.
5. Atualize a documentação pertinente e crie um commit para essa melhoria.
6. Repita o processo para as demais etapas e informe os resultados.

Não crie testes que apenas repitam a implementação. Mudanças de comportamento
precisam de verificações que detectem regressões, usando as fixtures existentes.
Alterações apenas de documentação devem ter conteúdo, links e diff revisados.
Não informe que um teste passou quando ele não foi executado.

Use os comandos de [CONTRIBUTING.md](../CONTRIBUTING.md). Ruff e suas regras são
definidos em pyproject.toml; a versão instalada vem do uv.lock. Não introduza outro
formatador ou regras paralelas sem uma necessidade discutida na tarefa.
Atualize dependências e o lockfile com uv quando necessário ao escopo; evite
atualizações de pacotes sem relação com a mudança solicitada.

## Organização e dados

Siga o [layout aceito](architecture/adr-001-directory-layout.md), mantendo a raiz
com metadados, documentação principal e os adaptadores legados. Novos arquivos
temporários devem ficar em .cache, não em diretórios novos espalhados na raiz.

Mudanças de caminhos, preferências ou formatos de dados precisam preservar as
instalações existentes e incluir testes de migração. Não use reuniões reais ou
credenciais para testes. Consulte [o guia de dados](storage.md) para migrações,
conflitos, backups e compatibilidade dos clientes MCP.

## Critério de versão

Use MAJOR.MINOR.PATCH quando uma publicação for solicitada:

| Incremento | Critério |
| --- | --- |
| MAJOR | Quebra da interface pública suportada que exige adaptação do usuário ou cliente. |
| MINOR | Funcionalidade ou comando novo, mantendo compatibilidade das entradas existentes. |
| PATCH | Correção de comportamento compatível, sem funcionalidade pública nova. |

Refatoração interna não exige MAJOR por si só. Documentação, CI e ajustes de
formatação podem acompanhar a próxima release, sem criar uma versão isolada.
Avalie o conjunto desde a última tag publicada, não apenas o último commit.
Explique a escolha da versão antes de publicar.

A 2.2.0 exemplifica MINOR: reuniu novos comandos, organização dos diretórios,
migração dos dados e CI, preservando os adaptadores antigos de execução.

## Publicar uma versão

Com a publicação autorizada para a tarefa:

1. Confira as tags e releases remotas, a branch e o estado do Git.
2. Atualize a versão em pyproject.toml, sincronize uv.lock com uv e alinhe o
   cabeçalho do README. Adicione a entrada em CHANGELOG com data, comportamento,
   instruções de atualização e validação efetivamente realizada.
3. Execute lint, formatação, suíte completa e construção do wheel. Para mudanças
   de estrutura ou comandos, valide também as entradas instaladas e o pacote.
4. Registre o commit de versão e envie os commits da tarefa, preservando os
   commits individuais das etapas anteriores.
5. Aguarde o sucesso do CI correspondente ao SHA enviado. Investigue falhas antes
   de continuar; não reduza as verificações para esconder problemas.
6. Crie a tag anotada vMAJOR.MINOR.PATCH no commit validado e publique a release
   no GitHub com as notas do CHANGELOG. Não substitua uma tag já publicada.
7. Confira se release, tag, commit remoto e CI correspondem entre si. Informe
   o link da release e a situação final do repositório.

Esses passos registram o procedimento; não autorizam novas publicações por conta
própria. Para tarefas sem pedido de publicação, entregue os commits locais e
informe que ainda não foram enviados.
