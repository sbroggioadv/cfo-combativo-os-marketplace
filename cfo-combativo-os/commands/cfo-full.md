---
description: Pipeline completo de fechamento — ingere, concilia, analisa (fluxo de caixa + KPIs + provisoes), detecta anomalias, audita R1-R4, gera dashboard e monta o pacote de triagem contabil. PARA antes do envio (gate humano) — o disparo a contabilidade so acontece em /cfo-enviar com confirmacao explicita. Nunca envia automaticamente.
allowed-tools: Read, Write, Edit, WebFetch, WebSearch, Bash, Glob, Grep
argument-hint: "entidade(s) + competencia + recorte (ou --total)"
---

Voce foi acionado pelo comando `/cfo-full` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** rodar o fechamento de ponta a ponta — **parando antes do envio** (gate, premortem C5).

## PIPELINE (Cenario E do cfo-master)

1. **Acionar `cfo-master`** com intencao `full`.
2. Sequencia:
   ```
   1. ingest-*            (extrato/notas/produtos → schema canonico §3)
   2. conciliacao-bancaria (marca is_transferencia_intragrupo)
   3. fluxo-de-caixa + indicadores-kpi + provisoes
   4. deteccao-anomalias
   5. auditoria-cfo        (R1-R4 — obrigatorio)
   6. dashboard-html
   7. triagem-contabil     (monta o pacote por competencia)
   → PARA.
   ```
3. Ao final, exibe: pacote montado + diagnostico + dashboard, e a frase:
   > "Pacote pronto. O envio a contabilidade NAO foi disparado — use `/cfo-enviar` e confirme o disparo manualmente."

## REGRA DURA — GATE (trava 2, premortem C5)

O `/cfo-full` **NUNCA** envia e-mail. Monta tudo e **para antes do passo de envio**. Nao existe caminho automatico para o conector externo. Envio so via `/cfo-enviar` com confirmacao explicita do operador. `auditoria-cfo` R3 verifica que o gate foi respeitado.

## OUTRAS REGRAS DURAS

1. **Degradacao graciosa** — se uma lib de parser faltar, o passo declara e instrui `pip install`, sem quebrar o pipeline (premortem C2).
2. **Nunca fabricar** taxa/indice — indisponivel → declara (trava 4).
3. **Por recorte** — entidade/grupo/total explicito em cada etapa.

**Skill a acionar:** `cfo-master` (intencao full).
