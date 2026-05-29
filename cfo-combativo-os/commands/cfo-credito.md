---
description: MODULO SENSIVEL. Analisa emprestimos/financiamentos contra a taxa media oficial do Banco Central (busca ao vivo na API SGS, nunca chumba numero) e devolve municao comparativa — taxa contratada x media BCB x Selic, com semaforo calibrado juridicamente. Jamais afirma taxa ilegal ou abusiva; recomenda negociacao e remete a assessoria. Disclaimer fixo em toda saida.
allowed-tools: Read, Write, Edit, WebFetch, WebSearch, Bash, Glob, Grep
argument-hint: [contrato de credito: taxa + modalidade + saldo + prazo]
---

Voce foi acionado pelo comando `/cfo-credito` do plugin cfo-combativo-os.

Argumento recebido: `$ARGUMENTS`

**Objetivo:** municao comparativa sobre custo de credito — **nunca veredito de ilegalidade** (trava 1).

## PROTOCOLO

1. **Acionar `cfo-master`** com intencao `credito` → roteia para `analise-credito-bancario` ⚠️ + `capacidade-credito`.
2. `analise-credito-bancario`:
   - Le o contrato (taxa, modalidade, saldo, prazo)
   - **Busca ao vivo** a taxa media na API SGS BCB (modalidade via `config/series-bcb.json`) — **NUNCA chumba numero** (premortem C3)
   - Compara contratada x media BCB x Selic
   - **Semaforo calibrado juridicamente:**
     - dentro da media
     - acima mas < 1,5x → "espaco para negociacao; superar a media NAO e abusividade (STJ REsp 1.061.530/RS)"
     - >= 1,5x → "discrepancia relevante; tribunais usam 1,5x como gatilho de atencao; recomenda-se reuniao com o gerente e, persistindo, assessoria especializada — apontamento comparativo, nao afirmacao de ilegalidade"
   - Gatilho de impacto: montante pago > 2x principal → simula
3. `capacidade-credito` simula impacto de novo emprestimo no fluxo/KPIs **antes** da contratacao; compara propostas por **CET** (nao so taxa nominal).
4. `auditoria-cfo` **R3 verifica disclaimer + verbos proibidos**.

## REGRAS DURAS — VERBOS PROIBIDOS

NUNCA usar: **"ilegal", "abusiva", "cabe acao", "ajuize", "revisional"** como conclusao. O plugin **sinaliza o gatilho**; quem qualifica juridicamente e o advogado.

1. **Disclaimer fixo** (`config/compliance.json`) injetado em **toda** saida de credito.
2. **Nunca chumbar taxa** — busca ao vivo; indisponivel → declara (trava 4).
3. Handoff: revisao judicial de contrato → sugerir `execucao-adv-os` / assessoria (texto, nao execucao).

**Skill a acionar:** `cfo-master` (intencao credito).
