---
description: Benchmark de precos — valida preco vs custo vs margem, identifica margem negativa, abaixo do break-even ou fora da faixa da categoria, e gera ranking por saude de margem com simulacao de impacto de reprecificacao no resultado. Pesquisa de faixa de referencia de mercado so com autorizacao do operador.
allowed-tools: Read, Write, Edit, WebFetch, WebSearch, Bash, Glob, Grep
argument-hint: [tabela de produtos ja ingerida | produto/categoria especifico]
---

Voce foi acionado pelo comando `/cfo-precos` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** validar precos e saude de margem.

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `precos` → roteia para `benchmark-precos`.
2. Pre-requisito: tabela de produtos ingerida (`ingest-tabela-produtos`). Se ausente, o orquestrador pede o arquivo primeiro.
3. A skill cruza **margem x custo x preco**, identifica:
   - margem **negativa**
   - preco **abaixo do break-even**
   - preco **fora da faixa** da categoria
4. Saida: **ranking por saude de margem** + sugestao de reprecificacao com **simulacao de impacto no resultado**.
5. `auditoria-cfo` antes de entregar.

## REGRAS DURAS

1. **Pesquisa web de faixa de mercado SO com autorizacao explicita** do operador.
2. **Nunca fabricar** preco de referencia de concorrente — declarar a fonte ou a indisponibilidade.
3. Simulacao de reprecificacao e **munica decisoria**, nao recomendacao impositiva.

**Skill a acionar:** `cfo-master` (intencao precos) → `benchmark-precos`.
