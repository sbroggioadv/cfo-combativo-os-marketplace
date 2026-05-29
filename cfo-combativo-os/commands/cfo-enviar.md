---
description: GATE DE ENVIO. Unica acao do plugin que toca conector externo (MCP Gmail/Outlook). Monta o e-mail para a contabilidade (destinatario do state, assunto, corpo, anexos) e SO dispara apos confirmacao explicita do operador. Sem confirmacao, instrui o envio manual. Nunca automatico, nunca agendado.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: [competencia do pacote ja montado em /cfo-contabil]
---

Voce foi acionado pelo comando `/cfo-enviar` 🔒 do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** enviar o pacote a contabilidade — **com gate de confirmacao humana** (trava 2).

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `envio` → roteia para `envio-contabilidade` 🔒 (a UNICA skill que toca conector externo — premortem C5).
2. Pre-requisito: pacote ja montado por `/cfo-contabil`. Se ausente, montar primeiro (sem enviar).
3. A skill monta o e-mail: destinatario = `contabilidade.email` do `cfo-state.json`, assunto, corpo, anexos do pacote.
4. **Exibe e PARA:**
   > "O envio a contabilidade deve ser precedido de aviso. Confirma o disparo agora? (Anexos: [lista]. Destinatario: [mascarado].)"
5. **SO com confirmacao explicita** dispara via MCP Gmail/Outlook.
6. **Sem confirmacao** → instrui envio manual + aponta o pacote pronto no disco.
7. `auditoria-cfo` R3 verifica que o gate foi respeitado.

## REGRAS DURAS — INEGOCIAVEIS

1. **NUNCA** envio automatico ou agendado — sempre exige `s` explicito do operador.
2. **NUNCA** disparar conector fora desta skill.
3. **Mascarar** destinatario e dados sensiveis na previa exibida.
4. Se o `cfo-state.json` nao tem e-mail da contabilidade, **perguntar** — nunca supor destinatario.

**Skill a acionar:** `cfo-master` (intencao envio) → `envio-contabilidade` 🔒.
