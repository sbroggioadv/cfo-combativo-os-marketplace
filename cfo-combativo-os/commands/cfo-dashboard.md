---
description: Gera dashboard HTML single-file standalone (sem servidor, sem localStorage, dados injetados na geracao) com KPI cards semaforicos, fluxo de caixa com projecao e alerta de ruptura, aging AP/AR, benchmark de credito BCB com disclaimer fixo, saude de margem por produto e seletor de recorte multi-entidade (entidade/grupo/total). Responsivo, pronto para impressao/PDF.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + periodo + recorte | --total]
---

Voce foi acionado pelo comando `/cfo-dashboard` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** dashboard visual single-file standalone (design-spec §8).

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `dashboard` → roteia para `dashboard-html`.
2. A skill gera **single-file HTML** auto-contido (engine `scripts/lib/dashboard_generator.py`; referencia visual fiel em `templates/dashboard-reference.html`):
   - **Painel resumo executivo** — KPI cards semaforicos
   - **Fluxo de caixa** — linha + projecao + alerta de ruptura
   - **Aging AP/AR** — barras
   - **Benchmark de credito BCB** — tabela + **disclaimer fixo**
   - **Saude de margem** por produto
   - **Seletor de recorte multi-entidade** — entidade / grupo / total (§2.3)
3. Identidade visual canonica: `--base:#101010; --surface:#1a1a1a; --lime:#CCFF00; --text:#f2f2f2`. Chart.js via CDN (com nota de fallback offline).
4. `auditoria-cfo` R4 confere que os paineis pedidos foram cobertos e os recortes estao corretos.

## REGRAS DURAS

1. **Sem servidor, sem localStorage** — dados injetados na geracao.
2. **Indice/taxa indisponivel** → o dashboard **declara** ("media BCB indisponivel em DD/MM — reexecutar"), nunca estima (trava 4 / premortem C3).
3. **Fronteira PF↔PJ explicita** no seletor de recorte.
4. Responsivo e pronto para impressao/PDF.

**Skill a acionar:** `cfo-master` (intencao dashboard) → `dashboard-html`.
