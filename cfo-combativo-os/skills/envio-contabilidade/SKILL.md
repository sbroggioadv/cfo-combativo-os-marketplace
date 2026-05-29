---
name: envio-contabilidade
description: >
  ENVIO-CONTABILIDADE — GATE de envio (trava 2). UNICA skill do plugin
  que toca um conector externo (MCP Gmail/Outlook). Monta o e-mail para a
  contabilidade (destinatario do cfo-state.json, assunto, corpo, anexos do
  pacote da triagem) e SEMPRE para no texto de confirmacao do
  config/compliance.json (gate_envio_contabilidade), so disparando com "s"
  explicito do operador. Sem confirmacao, NAO envia nada e instrui o envio
  manual apontando o pacote pronto. NUNCA envio automatico ou agendado
  (premortem C5). Use quando o operador disser "enviar para a
  contabilidade", "manda pro contador", "dispara o pacote contabil",
  "enviar o fechamento do mes", "/cfo-enviar".
---

# ENVIO-CONTABILIDADE 🔒 — Gate de Envio Externo

## 1. ESCOPO

Esta e a **unica** skill do plugin que toca um conector externo. Tudo o
mais e 100% local (trava 3). Por isso, ela e governada pela **trava 2**:
**nenhum e-mail e disparado automaticamente**. Monta, mostra, **para**, e
so envia com confirmacao explicita do operador.

NAO conhece o conteudo financeiro (isso e `triagem-contabil`), NAO decide
sozinha enviar, NAO agenda envio futuro.

## 2. INPUT NECESSARIO

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `entidade_id` | sim | Entidade do pacote — **PERGUNTAR** se ausente |
| `competencia` | sim | Mes do pacote a enviar |
| `pacote_path` | derivado | Da `triagem-contabil` (`.cfo/.../triagem/{comp}/`) |
| `destinatario` | derivado | `contabilidade.email` do `cfo-state.json` |

Pre-requisito: `triagem-contabil` ja montou o pacote. Se nao ha pacote →
roteia para montar a triagem primeiro (`/cfo-contabil`).

## 3. PROCESSAMENTO

### Passo 1 — Localizar o pacote e o destinatario

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-state.py --get-contabilidade
```

- Le `contabilidade.nome` / `contabilidade.email` do state.
- Localiza o pacote da competencia montado pela `triagem-contabil`.
- Se nao ha e-mail de contabilidade cadastrado → pede ao operador (ou
  roteia para `/cfo-setup`). Sem destinatario, nao ha o que enviar.
- Se nao ha pacote → instrui rodar `/cfo-contabil` primeiro.

### Passo 2 — Montar o e-mail (SEM enviar)

Monta, em memoria, mas **NAO dispara**:
- **Para:** `contabilidade.email` (mascarado na exibicao).
- **Assunto:** `Documentos contabeis — {{entidade}} — {{competencia}}`.
- **Corpo:** mensagem objetiva (entidade, competencia, lista de anexos,
  nota de que ha relatorio de pendencias).
- **Anexos:** arquivos do pacote da triagem (INDICE, pendencias,
  extratos, notas, conciliacao).

Exibe o e-mail montado para revisao do operador (destinatario mascarado,
assunto, resumo do corpo, lista de anexos).

### Passo 3 — GATE de confirmacao (trava 2 — INEGOCIAVEL)

Exibir **exatamente** o texto fixo do `config/compliance.json`, campo
`gate_envio_contabilidade`:

> *"O envio a contabilidade deve ser precedido de aviso previo a ela. O
> pacote esta montado e pronto. Confirma o disparo do e-mail AGORA? (s/n)
> — Sem confirmacao, nao envio nada e te mostro onde esta o pacote para
> envio manual."*

**E PARAR.** Aguardar resposta do operador. Sem `s` explicito, NAO envia.

### Passo 4 — Disparar SOMENTE com "s" explicito

- **Operador responde "s"** → e so entao chamar o conector externo:
  - MCP Gmail (`create_draft` + envio) ou MCP Outlook, conforme
    `tools.email_provider` do state.
  - Confirmar o envio com o ID/retorno do conector.
- **Operador responde "n" / qualquer coisa que nao seja "s" / silencio**
  → **NAO envia**. Instruir envio manual:
  - *"Nao enviei nada. O pacote esta pronto em
    `<cwd>/.cfo/entidades/{id}/triagem/{competencia}/`. Anexe esses
    arquivos e envie manualmente para a contabilidade quando quiser."*

NUNCA ha caminho automatico. `/cfo-full` monta tudo mas **para antes
deste envio** — quem chega aqui sempre passa pelo gate (premortem C5).

## 4. OUTPUT

### Antes da confirmacao (sempre)

```markdown
## 🔒 Pronto para enviar — {{entidade}} · {{competencia}}

**Para:** [con***@***.com] · **Assunto:** Documentos contabeis — ...
**Anexos:** INDICE.md, RELATORIO-PENDENCIAS.md, extratos/, notas/, conciliacao.csv

> O envio a contabilidade deve ser precedido de aviso previo a ela. O
> pacote esta montado e pronto. **Confirma o disparo do e-mail AGORA?
> (s/n)** — Sem confirmacao, nao envio nada e te mostro onde esta o
> pacote para envio manual.
```

### Depois de "s"

```markdown
## ✅ Enviado
E-mail disparado para [con***@***.com] via [Gmail]. ID: [...].
Competencia {{competencia}} da {{entidade}} entregue.
```

### Depois de "n" / sem confirmacao

```markdown
## ⏸️ Nao enviei nada
O pacote esta pronto em:
`<cwd>/.cfo/entidades/{{id}}/triagem/{{competencia}}/`
Anexe esses arquivos e envie manualmente quando quiser.
```

## 5. PROIBICOES

1. **Nunca** enviar sem `s` explicito do operador (trava 2 — premortem C5).
2. **Nunca** envio automatico, agendado ou em pipeline (`/cfo-full` para
   antes daqui).
3. **Nunca** interpretar silencio, "ok", "pode", "talvez" como `s` — so
   `s` explicito autoriza.
4. **Nunca** exibir e-mail/conta de contabilidade sem mascarar.
5. **Nunca** alterar/suavizar o texto fixo do gate (compliance.json).
6. **Nunca** propagar excecao de conector/import ao Cowork — falha de
   conector vira instrucao de envio manual (degradacao graciosa, C2).
7. **Nunca** tocar conector externo fora desta skill (e a unica).

## 6. INTEGRACAO

- **Upstream:** `triagem-contabil` (`/cfo-contabil`) monta o pacote.
- **Conector:** MCP Gmail/Outlook (`tools.email_provider` do state).
- **Auditoria:** `auditoria-cfo` R3 verifica que o gate foi respeitado.
