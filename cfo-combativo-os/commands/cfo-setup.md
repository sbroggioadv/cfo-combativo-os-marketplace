---
description: Inicia o wizard de configuracao do plugin cfo-combativo-os — monta ou edita o grafo multi-entidade (PF, PJ ou ambos; N entidades; N contas por entidade; grupos opcionais). Editavel a qualquer tempo, append-only, nunca apaga o consolidado ja construido.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [--update para editar o grafo | --add-entidade | --add-conta]
---

Voce foi acionado pelo comando `/cfo-setup` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** configurar o **grafo multi-entidade** do operador (design-spec §2).

## PROTOCOLO

1. **Acionar a skill `cfo-onboarding`** imediatamente — ela conduz o wizard completo.
2. O wizard pergunta e grava em `<cwd>/.cfo/cfo-state.json` (via `scripts/state.py`):
   - **Perfil:** PF, PJ ou ambos?
   - **Entidades:** quantas? cada uma — nome/apelido, tipo (pf/pj), documento (gravado **mascarado**), regime tributario (se PJ: simples/presumido/real), data de inicio no sistema
   - **Contas por entidade:** N contas correntes / cartoes / investimento (banco + tipo + apelido) — o operador pode ter 20 contas
   - **Grupos (opcional):** agrupamento livre (ex.: grupo-empresas, grupo-familia)
   - **Contabilidade:** nome + e-mail do contador + `avisar_antes_envio=true`
   - **Preferencias:** `recorte_default` (entidade/grupo/total), moeda, mascaramento em log
3. Cria tambem `<cwd>/.cfo/entidades/{id}/base.sqlite` (historico consolidado mes a mes, vazio no setup).

## REGRA DURA — APPEND-ONLY (trava §2.4)

O grafo e **alteravel a qualquer tempo SEM perder o consolidado ja construido** — so **agrega**:

- Adicionar entidade nova no mes 7 **nao invalida** os meses 1-6 das outras.
- Reprocessar um mes **substitui so aquele mes** (idempotencia por `(entidade, conta, competencia)`), nunca faz rebuild destrutivo.
- `state.py` faz **backup antes de salvar**.
- Se ja existir `cfo-state.json`, a skill oferece **continuar / adicionar / reconfigurar** (idempotencia).
- Argumento `--update` vai direto ao fluxo de edicao; `--add-entidade` / `--add-conta` agregam sem perguntar tudo de novo.

## ATENCAO LGPD (trava 3)

A skill emite **aviso LGPD na 1a vez por entidade** e alerta se `<cwd>/.cfo/` estiver em pasta sincronizada (iCloud / OneDrive / Dropbox / Drive) — extratos, OFX e NF-e sao dados financeiros sob LGPD e parte e sigilo bancario (LC 105/2001). Pasta sincronizada = risco de vazamento. `.cfo/` ja vai no `.gitignore`.

**Skill a acionar:** `cfo-onboarding`.
