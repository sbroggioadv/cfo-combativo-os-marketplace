---
description: Painel de KPIs de CFO — liquidez (corrente/seca/imediata), endividamento (geral, Divida Liq./EBITDA, cobertura de juros), prazos e ciclo (PMR/PMP/PME, ciclo financeiro), rentabilidade (margem bruta/EBITDA/liquida, ROI/ROE/ROA/ROIC) e operacional (break-even, giro, ticket medio). Cada KPI com leitura semaforica e comentario de CFO.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + periodo | KPI especifico]
---

Voce foi acionado pelo comando `/cfo-kpi` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** painel de indicadores financeiros de CFO com leitura semaforica.

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `kpi` → roteia para `indicadores-kpi`.
2. A skill calcula (formulas + faixas em `config/indicadores.json`, engine pesado em `scripts/lib/kpi_engine.py`):
   - **Liquidez:** corrente, seca, imediata
   - **Endividamento:** geral, Divida Liquida/EBITDA, alavancagem, cobertura de juros (ICSD)
   - **Prazos/ciclo:** PMR, PMP, PME, ciclo financeiro, ciclo de conversao de caixa
   - **Rentabilidade:** margem bruta/EBITDA/liquida, ROI, ROE, ROA, ROIC
   - **Operacional:** break-even, giro de ativos/estoque, ticket medio, NCG
3. Cada KPI recebe **leitura semaforica** (verde/amarelo/vermelho) + **comentario de CFO** (o que significa, o que fazer).
4. `auditoria-cfo` (R2 confere formulas, nenhum numero fabricado).

## REGRAS DURAS

1. **Formulas vem de `config/indicadores.json`** — nunca improvisar conta de KPI.
2. **Faixa semaforica explicita** — verde/amarelo/vermelho com o limiar usado.
3. **Por recorte** (entidade/grupo/total) — KPI de grupo elimina transferencia intragrupo.

**Skill a acionar:** `cfo-master` (intencao kpi).
