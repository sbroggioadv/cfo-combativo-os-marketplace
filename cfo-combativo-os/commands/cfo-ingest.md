---
description: Importa dados financeiros brutos para o schema canonico de transacao — extratos bancarios/cartao (OFX/QFX/CSV/XLSX), NF-e/NFS-e (XML) e tabela de produtos/precos. Toda transacao recebe entidade + conta. Persistencia append-only por competencia, degradacao graciosa se a lib faltar.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [caminho do arquivo OFX/CSV/XLSX/XML + a qual entidade/conta pertence]
---

Voce foi acionado pelo comando `/cfo-ingest` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** ler dados brutos e normalizar para o schema canonico (design-spec §3).

## PROTOCOLO

### 1. Acionar `cfo-master` (que decide qual skill de ingestao)

Use `Skill(skill="cfo-master")` com intencao `ingestao`. O orquestrador roteia conforme o tipo de arquivo:

| Entrada | Skill |
|---|---|
| extrato/cartao OFX, QFX, CSV, XLSX | `ingest-extrato-bancario` |
| NF-e / NFC-e / NFS-e (XML) | `ingest-notas-fiscais` |
| tabela de produtos/servicos e precos (XLSX/CSV) | `ingest-tabela-produtos` |

### 2. Vinculo obrigatorio entidade + conta

Toda transacao recebe `entidade_id` + `conta_id` do grafo (§2). Se a conta nao estiver clara, **perguntar a qual conta do grafo pertence** antes de gravar — nunca supor.

### 3. Persistencia append-only por competencia (trava §2.4)

Grava no `base.sqlite` da entidade. Reprocessar um mes **substitui so aquele mes** (idempotencia por `(entidade, conta, competencia)`) — nunca destroi o historico das outras entidades/meses.

### 4. Degradacao graciosa (premortem C2)

Parser tenta a lib (`ofxparse`/`nfelib`/`pandas`) → se ausente, fallback stdlib (`xml.etree`, `csv`) → se impossivel, **declara e instrui `pip install`**. NUNCA quebra a sessao.

## REGRAS DURAS

1. **Schema canonico §3** — toda transacao normalizada antes de qualquer analise.
2. **Dedup idempotente** por hash sha256 de `(entidade+conta+data+valor+descricao)`.
3. **Mascarar** conta/CPF/CNPJ/saldo em qualquer log (trava 3).
4. **Nunca preencher coluna ausente por suposicao** — perguntar (PA-14).

**Skill a acionar:** `cfo-master` (intencao ingestao).
