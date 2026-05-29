---
name: cfo-onboarding
description: >
  CFO-ONBOARDING — Comando `/cfo-setup`. Monta e edita o GRAFO
  MULTI-ENTIDADE do plugin cfo-combativo-os (design-spec §2): perfil
  (PF / PJ / ambos) → entidades (nome, tipo, doc mascarado, regime
  tributario se PJ, N contas correntes/cartoes/investimentos) → grupos
  opcionais (grupo-empresas, grupo-familia) → contabilidade (nome, e-mail,
  avisar antes de enviar) → tools declaradas → aviso LGPD/sigilo bancario.
  Grava em <cwd>/.cfo/cfo-state.json via `python3 scripts/state.py`.
  EDITAVEL A QUALQUER TEMPO e APPEND-ONLY — adicionar entidade/conta/grupo
  NUNCA apaga o consolidado ja construido, so agrega (trava §2.4). Use
  SEMPRE na primeira sessao OU quando o gestor disser "configurar",
  "primeira vez", "/cfo-setup", "adicionar empresa", "adicionar conta",
  "nova entidade", "criar grupo", "trocar contabilidade", "editar meu setup".
---

# CFO-ONBOARDING — Grafo Multi-Entidade

## 1. ESCOPO

Cria/edita o **grafo de entidades e grupos** em `<cwd>/.cfo/cfo-state.json`
(STATE SCHEMA do design-spec §6). Esse grafo e o coracao do plugin: o
gestor pode ser PF, PJ ou ambos, ter **multiplas entidades simultaneas**
(a PF dele + a PF do conjuge + N empresas), cada uma com **N contas**.

Toda skill de analise resolve entidade/conta/recorte a partir deste grafo.
**Pre-requisito de tudo.** Sem grafo (`wizard_state.completed=false`), o
`cfo-master` roda esta skill primeiro.

```
GRUPO (opcional)        ENTIDADE                 CONTA
grupo-empresas   ──┬──  empresa-alfa (PJ)  ──┬─  itau-cc-001
                  └──  empresa-beta  (PJ)  └─  bb-cc-002
grupo-familia    ──┬──  joao         (PF)  ──┬─  nubank-001
                  └──  maria        (PF)  └─  c6-cc-002
```

## 2. ⭐ REGRA DURA — APPEND-ONLY (trava §2.4)

> Esta e a promessa estrutural do plugin. Repetir ao gestor.

- O grafo e **editavel a qualquer tempo** — adicionar entidade, conta ou
  grupo; reclassificar — **sem perder o consolidado ja construido**.
- Adicionar a `empresa-gama` no mes 7 **nao invalida** os meses 1-6 das
  outras entidades. O grafo evolui; o historico e **monotonico**.
- `state.py` faz **backup antes de salvar** e escreve atomicamente.
  Nenhuma edicao do grafo faz rebuild destrutivo do `base.sqlite` das entidades.
- Em edicao, **so agrega** — nunca `init` por cima de grafo existente.

## 3. QUANDO RODAR

- Primeira sessao (`cfo-state.json` ausente ou `wizard_state.completed=false`)
- Comando explicito `/cfo-setup`
- Gestor disse: "adicionar empresa/conta", "nova entidade", "criar grupo",
  "trocar contabilidade", "mudar recorte default", "editar setup"

## 4. PASSO 0 — AVISO LGPD (CRITICO, 1ª vez por workdir)

Texto fixo de `config/compliance.json` → `lgpd_aviso_primeira_execucao`:

```
⚠️ AVISO DE PRIVACIDADE (LGPD + sigilo bancario LC 105/2001)

Extratos, notas fiscais e dados pessoais que voce fornecer sao DADOS
PESSOAIS (LGPD) e parte e protegida por sigilo bancario. Tudo e
processado LOCALMENTE na sua maquina. Nada e transmitido sem uma acao
deliberada sua. Logs nao registram conta, CPF/CNPJ completo ou saldo em
texto plano.

A pasta `.cfo/` que vou criar guardara o grafo + historico financeiro.
NAO rode este plugin com cwd dentro de:
- iCloud Drive (~/Library/Mobile Documents/...)  - Google Drive
- Dropbox  - OneDrive  - Documents/Desktop/Downloads

Sua sessao esta em: <cwd atual>
Confirma que entende e autoriza o processamento local destes dados? (s/n)
```

Se o cwd contem `iCloud`/`Google Drive`/`Dropbox`/`OneDrive`/
`Mobile Documents`/`CloudDocs` → **PARAR** e pedir troca de cwd.
Ao confirmar: gravar `preferences.lgpd_aviso_aceito=true`.

## 5. WIZARD — UMA PERGUNTA POR VEZ

### Passo 1 — Perfil
```
Voce vai gerir:
  (1) so PF (pessoa fisica)
  (2) so PJ (empresa)
  (3) ambos (PF + PJ — recomendado pra quem tem holding/socio)
```
→ grava `perfil`.

### Passo 2 — Entidades (repetir por entidade)
```
Vamos cadastrar a entidade.
 a) Nome/apelido? (ex: "Empresa Alfa Ltda", "Joao")
 b) Tipo? (pf | pj)
 c) Documento (CPF/CNPJ)? — vou GUARDAR MASCARADO (ex: **.***.**8/0001-**)
 d) [se PJ] Regime tributario? (simples | presumido | real | nao sei agora)
 e) Mes de inicio no sistema? (YYYY-MM — de quando vamos consolidar)
 f) Contas dessa entidade (pode ter varias):
    - apelido (ex: "Itau PJ"), banco (itau|bb|bradesco|santander|
      nubank|inter|c6|caixa|...), tipo (cc|cartao|investimento)
    Adicionar outra conta? (s/n)
Adicionar outra entidade? (s/n)
```
- `id` da entidade/conta = slug kebab-case auto-derivado (`empresa-alfa`,
  `itau-cc-001`), validado por `state.py` (regex `^[a-z0-9]+(-[a-z0-9]+)*$`).
- Documento (CPF/CNPJ) gravado **mascarado** (nunca completo) — trava §3.

### Passo 3 — Grupos (opcional)
```
Quer agrupar entidades? (ex: "grupo-empresas" junta alfa+beta;
"grupo-familia" junta voce+conjuge). Grupos permitem ver a soma do
grupo eliminando transferencias entre as entidades dele.
 - Criar grupo? nome + tipo (pj|pf) + quais entidades entram?
Uma entidade pertence a 0 ou 1 grupo (v0.1.0).
```

### Passo 4 — Contabilidade
```
Tem contabilidade que recebe o pacote mensal?
 - Nome? E-mail? (opcional)
 - Avisar antes de qualquer envio? (default SIM — trava 2, gate humano)
```
→ grava `contabilidade{}`. Envio nunca e automatico.

### Passo 5 — Tools declaradas (opcional)
```
Quais ferramentas voce usa? (so declara — nao conecta nada agora)
 - provedor de e-mail (gmail/outlook) - banco/PSP - sistema contabil
```
→ grava `tools{}`.

### Passo 6 — Preferencias
```
Recorte default das analises?
 (1) total consolidado (default)  (2) por entidade  (3) por grupo
```
→ grava `preferences.recorte_default`. Moeda BRL, idioma pt-BR por default.

## 6. CONFIRMACAO + PERSISTENCIA

Mostrar resumo do grafo (entidades, contas mascaradas, grupos, recorte
default) → "Posso gravar em `<cwd>/.cfo/cfo-state.json`? (s/n)".

Gravar via `state.py` (degradacao graciosa — se Python indisponivel,
instruir e nunca quebrar a sessao):
```bash
# 1a vez (grafo novo):
python3 scripts/state.py init <cwd> --perfil ambos
python3 scripts/state.py set <cwd> preferences.recorte_default total
python3 scripts/state.py set <cwd> preferences.lgpd_aviso_aceito true
# grupos (opcional) — agregados append-only, idempotentes por id:
python3 scripts/state.py add-grupo <cwd> --id grupo-empresas --nome "Grupo de Empresas" --tipo pj
python3 scripts/state.py add-grupo <cwd> --id familia --nome "Familia" --tipo pf
# entidades — agregadas append-only (re-rodar atualiza campos, nunca apaga contas/outras):
python3 scripts/state.py add-entidade <cwd> --id alfa --tipo pj --nome "Empresa Alfa" --regime simples --grupo grupo-empresas --inicio 2026-01
python3 scripts/state.py add-entidade <cwd> --id joao --tipo pf --nome "Joao" --grupo familia --inicio 2026-01
# contas de cada entidade — N contas, agregadas append-only por id:
python3 scripts/state.py add-conta <cwd> --entidade alfa --id itau-001 --banco itau --tipo cc --apelido "Itau PJ"
python3 scripts/state.py validate <cwd>   # deve passar
python3 scripts/state.py show <cwd>        # confere o grafo
```
Ao concluir: `wizard_state.completed=true`. `state.py` faz backup antes
de salvar e valida o grafo (slugs unicos, grupo_id existente, regime valido).

## 7. EDICAO DE GRAFO EXISTENTE (APPEND-ONLY)

Se `cfo-state.json` ja existe:
```
Grafo ja configurado (ultima atualizacao: <data>). O que editar?
 1. Adicionar entidade (nao apaga as existentes)
 2. Adicionar conta a uma entidade
 3. Criar/editar grupo
 4. Trocar contabilidade / tools
 5. Mudar recorte default
 6. Reclassificar entidade em grupo
 7. Cancelar
```
- Toda edicao **agrega** — nunca `init`, nunca rebuild.
- Confirmar que o consolidado historico das entidades existentes
  **permanece intacto** (so o grafo muda; o `base.sqlite` de cada entidade
  nao e tocado pela edicao de grafo).

## 8. OUTPUT FINAL

```yaml
grafo:
  configurado: true
  arquivo: "<cwd>/.cfo/cfo-state.json"
  perfil: [pf|pj|ambos]
  entidades: [{id, tipo, doc_mascarado, regime, grupo_id, contas:[...]}]
  grupos: [{id, nome, tipo}]
  contabilidade: {nome, email, avisar_antes_envio: true}
  recorte_default: [total|entidade|grupo]
  lgpd_aviso_aceito: true
  status: pronto_para_uso
```
```
✅ Grafo configurado. Proximos passos:
- /cfo — pergunte em linguagem natural ("quanto posso gastar na alfa?")
- /cfo-ingest — importe extratos/notas (OFX/CSV/XLSX/NF-e)
- /cfo-consolidar — visao entidade/grupo/total
- Adicione entidades/contas a qualquer tempo: /cfo-setup (agrega, nao apaga)
```

## 9. PROIBICOES

1. Nao gravar grafo em pasta sync (iCloud/GDrive/Dropbox/OneDrive) — bloqueador LGPD.
2. Nao gravar CPF/CNPJ completo — sempre mascarado.
3. **Nunca rodar `init` por cima de grafo existente** — edicao e sempre append-only (agrega).
4. Nao perguntar tudo de uma vez — UMA pergunta por vez (UX).
5. Nao enviar dado a API externa — grafo fica em disco local; sem telemetria.
6. Nao quebrar a sessao se `state.py`/Python falhar — degradar e instruir.
7. Nao marcar envio automatico — `avisar_antes_envio` default true (trava 2).

## 💡 Proximos passos opcionais (sugestao, nao execucao)

| Proximo passo | Comando | Plugin necessario |
|---|---|---|
| Planejamento tributario formal por entidade | `/tributario` | `tributario-societario-adv-os` |
| Configurar persona juridica do escritorio | `/start` | `ia-combativa-adv-os` |

> Cada plugin Adv-OS tem onboarding proprio; todos seguem o mesmo padrao
> de aviso LGPD + estado local fora de sync de nuvem.
