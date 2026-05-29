---
description: Contas a pagar — agenda de vencimentos com urgencia ponderada por valor (vencidas/hoje/7d/30d), fornecedores recorrentes e ordem otima de pagamento quando o caixa e insuficiente (custo de atraso x criticidade).
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + periodo | "o que tenho a pagar este mes"]
---

Voce foi acionado pelo comando `/cfo-pagar` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** gestao de contas a pagar e ordem de pagamento.

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `pagar` → roteia para `contas-a-pagar`.
2. A skill produz:
   - **Agenda de vencimentos** com urgencia (vencidas / hoje / 7d / 30d) ponderada por valor
   - **Fornecedores recorrentes**
   - **Ordem otima de pagamento** quando o caixa nao cobre tudo (custo de atraso x criticidade)
3. Integra com `fluxo-de-caixa` (o que cabe pagar sem romper o caixa) e `auditoria-cfo`.

## REGRAS DURAS

1. Ordem de pagamento e **munica decisoria** — explicita o criterio (custo de atraso x criticidade), nao impoe.
2. **Por recorte** — AP de grupo elimina transferencia intragrupo.
3. **Mascarar** dados de fornecedor em log.

**Skill a acionar:** `cfo-master` (intencao pagar) → `contas-a-pagar`.
