---
description: Conciliacao bancaria — casa transacao x nota x lancamento por valor + data + contraparte. Sinaliza lancamento sem nota, nota sem pagamento, divergencia de valor e duplicidade. Marca transferencia intragrupo (contraparte = outra entidade do mesmo grupo) para nao contar 2x no consolidado.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + periodo a conciliar | --todas-entidades]
---

Voce foi acionado pelo comando `/cfo-conciliar` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** o **coracao da triagem** — casar extrato x nota x lancamento e separar conciliado x pendente.

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `conciliacao` → roteia para `conciliacao-bancaria`.
2. A skill casa transacao x nota x lancamento por **valor + data (janela) + contraparte (fuzzy)**.
3. Sinaliza pendencias: lancamento sem nota, nota sem pagamento, divergencia de valor, duplicidade.
4. **Marca `is_transferencia_intragrupo`** quando a contraparte e outra entidade do **mesmo grupo** (premortem C7) — esses lancamentos sao **eliminados** nos recortes grupo/total para nao inflar faturamento.
5. Separa **conciliado x pendente** para alimentar a triagem contabil.

## REGRAS DURAS

1. **Transferencia intragrupo nunca conta 2x** — fronteira PF↔PJ explicita.
2. **Pendencia nunca vira fato** — o que nao conciliou e sinalizado, nao "estimado".
3. Saida sempre passa por `auditoria-cfo` (R1 integridade) antes de virar relatorio.

**Skill a acionar:** `cfo-master` (intencao conciliacao) → `conciliacao-bancaria`.
