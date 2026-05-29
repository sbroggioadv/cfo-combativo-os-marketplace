---
description: Fluxo de caixa realizado + projetado com alerta de ruptura (data provavel de saldo negativo). Responde a pergunta-assinatura "quanto posso gastar este mes" como caixa livre real apos provisoes e contas a pagar do periodo, por recorte (entidade/grupo/total).
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [entidade + periodo | "quanto posso gastar esse mes na alfa"]
---

Voce foi acionado pelo comando `/cfo-caixa` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** fluxo de caixa + projecao + a pergunta-assinatura "quanto posso gastar este mes".

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `caixa` → roteia para `fluxo-de-caixa`.
2. `fluxo-de-caixa` calcula:
   - **Realizado** (extratos conciliados) por dia/semana/mes
   - **Projetado** (AP + AR agendados)
   - **Alerta de ruptura:** projeta saldo futuro e sinaliza a **data provavel de saldo negativo**
   - **Sazonalidade** vs mesmo mes do ano anterior (historico SQLite)
3. Para "quanto posso gastar este mes", o `cfo-master` combina tres skills:
   ```
   caixa_livre = saldo_atual + AR_a_receber - AP_a_pagar - provisoes_devidas - teto_orcado_restante
   ```
   (`fluxo-de-caixa` + `provisoes` + `orcamento`)
4. `auditoria-cfo` (R1-R4) antes de entregar.

## REGRAS DURAS

1. "Quanto posso gastar" **NAO** e saldo da conta — e caixa livre real apos compromissos.
2. **Sempre por recorte** (entidade isolada / grupo / total) — explicitar qual.
3. **Sempre apontar** provisoes comprometidas (13o, ferias, tributos, reserva PF) e a data de ruptura.

**Skill a acionar:** `cfo-master` (intencao caixa).
