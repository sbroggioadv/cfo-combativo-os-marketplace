---
description: Contas a receber — aging (a vencer / 1-30 / 31-60 / 61-90 / +90), ranqueia inadimplentes por valor x dias e gera fila de cobranca. Faz handoff (nao produz aqui) dos casos que justificam notificacao extrajudicial para o ecossistema, em vez de misturar escopo.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + periodo | "quem me deve"]
---

Voce foi acionado pelo comando `/cfo-receber` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** gestao de contas a receber e inadimplencia.

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `receber` → roteia para `contas-a-receber`.
2. A skill produz:
   - **Aging:** a vencer, 1-30, 31-60, 61-90, +90 dias
   - **Ranking de inadimplentes** por valor x dias
   - **Fila de cobranca** priorizada
3. `auditoria-cfo` antes de entregar.

## HANDOFF (compartimentacao de escopo)

Casos que justificam **notificacao extrajudicial / cobranca judicial** NAO sao produzidos aqui — sao **sinalizados** para o ecossistema (texto, nao execucao):

| Proximo passo | Comando | Plugin |
|---|---|---|
| Notificacao extrajudicial de inadimplente | `/execucao cobranca` | `execucao-adv-os` |
| Calcular debito atualizado p/ cobrar | `/calculos` | `calculosjudiciais-adv-os` |

## REGRAS DURAS

1. **Nao produzir peca de cobranca** — so diagnostico financeiro + fila. Peca = handoff.
2. **Mascarar** dados de devedor em log (trava 3).

**Skill a acionar:** `cfo-master` (intencao receber) → `contas-a-receber`.
