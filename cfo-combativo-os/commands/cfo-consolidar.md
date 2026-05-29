---
description: Consolidacao multi-entidade nos tres recortes de leitura — por entidade (visao individual), por grupo (soma das entidades eliminando transferencias intragrupo) e total consolidado (operador inteiro, com a fronteira PF-PJ sempre explicita). Base para holding e planejamento patrimonial.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: "recorte (entidade <id> | grupo <id> | total) + periodo"
---

Voce foi acionado pelo comando `/cfo-consolidar` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** os tres recortes de leitura do grafo multi-entidade (design-spec §2.3).

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `consolidar` → roteia para `consolidacao-multi-entidade`.
2. A skill le o grafo do `cfo-state.json` e produz os tres recortes:
   - **Por entidade** — visao individual (empresa-alfa isolada; joao isolado)
   - **Por grupo** — soma das entidades do grupo, **eliminando transferencias intragrupo** (nao conta 2x)
   - **Total consolidado** — visao do operador inteiro, **fronteira PF↔PJ sempre explicita** (relevante para holding/planejamento patrimonial)
3. Exibe a visao individual **ao lado** da consolidada.
4. `auditoria-cfo` **R4 confere recortes corretos + fronteira PF↔PJ + eliminacao intragrupo**.

## REGRAS DURAS (premortem C7)

1. **Transferencia intragrupo eliminada** nos recortes grupo/total — marcada em `is_transferencia_intragrupo` pela conciliacao.
2. **Fronteira PF↔PJ nunca borrada** — confusao patrimonial e risco de holding; sinalizar, nao mascarar.
3. **Append-only** — consolidar nao reescreve historico; le o que ja existe (§2.4).

**Skill a acionar:** `cfo-master` (intencao consolidar) → `consolidacao-multi-entidade`.
