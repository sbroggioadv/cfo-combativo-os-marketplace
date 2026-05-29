---
description: Triagem contabil — monta o pacote mensal para a contabilidade (extratos + notas + conciliacao do periodo), gera indice do pacote e relatorio de pendencias (o que falta, o que diverge) e empacota por competencia. NAO envia — o envio depende do gate de confirmacao em /cfo-enviar.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + competencia | --todas-entidades]
---

Voce foi acionado pelo comando `/cfo-contabil` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** montar o pacote mensal para a contabilidade.

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `triagem-contabil` → roteia para `triagem-contabil`.
2. A skill:
   - Seleciona **extratos + notas + conciliacao** do periodo
   - Gera **indice do pacote** + **relatorio de pendencias** (o que falta, o que diverge)
   - Empacota por **competencia** (pasta/zip organizado)
3. `auditoria-cfo` (R1 integridade — conciliacao fechou? buracos de periodo?).

## REGRA DURA — GATE DE ENVIO (trava 2)

Esta skill **monta o pacote, NAO envia**. O envio externo so acontece via `/cfo-enviar`, que **para no passo de confirmacao explicita**. Aqui a saida termina apontando o pacote pronto + instrucao de que o disparo depende de confirmacao em `/cfo-enviar`.

**Skill a acionar:** `cfo-master` (intencao triagem-contabil) → `triagem-contabil`.
