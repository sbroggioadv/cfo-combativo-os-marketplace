---
name: auditoria-cfo
description: >
  AUDITORIA-CFO — Revisao obrigatoria R1-R4 antes de QUALQUER entrega do
  plugin cfo-combativo-os (espelha a Suprema Corte dos plugins
  juridicos, mas financeira e agnostica). Quatro gates sequenciais:
  R1 INTEGRIDADE DE DADOS (arquivos lidos, buracos de periodo, conciliacao
  fechou, valor sem origem), R2 CORRECAO DE CALCULO (formulas de KPI
  conferidas, series BCB da modalidade certa e ao vivo, nenhuma
  taxa/indice fabricado), R3 CALIBRAGEM DE CONCLUSAO (nenhuma afirmacao
  de ilegalidade, municao rotulada, disclaimers, gate de envio, LGPD/
  mascaramento), R4 COMPLETUDE E APRESENTACAO (recortes entidade/grupo/
  total corretos, PF+PJ, dashboard cobre o pedido). Veredito visivel
  R1✓/R2✓/R3✓/R4✓ — APROVADO. Sem as quatro, saida RETIDA. Use sempre
  antes de entregar diagnostico, KPI, dashboard, analise de credito ou
  consolidacao; ou quando pedirem "audita", "revisa antes de entregar",
  "R1 R2 R3 R4", "confere esse calculo financeiro".
---

# AUDITORIA-CFO — Revisao R1-R4 (gate obrigatorio de entrega)

## 1. ESCOPO

Quatro gates sequenciais que rodam **depois** de qualquer skill de
analise gerar resultado e **antes** de o `cfo-master` entregar ao gestor.
Cada gate emite:
- ✅ **OK** (passa pro proximo)
- ⚠️ **REVISAR** (ajustar antes de entregar — recomendacao especifica)
- 🛑 **BLOQUEADO** (impede entrega — exige correcao)

Veredito final consolidado:
- **APROVADO** — os 4 gates OK
- **REVISAR** — ≥1 gate REVISAR, nenhum BLOQUEADO
- **RETIDO** — ≥1 gate BLOQUEADO; saida NAO vai ao gestor

**Regra dura:** sem `R1✓/R2✓/R3✓/R4✓ — APROVADO`, a saida fica retida.

## 2. INPUT NECESSARIO

Recebido por auto-chain do `cfo-master`:
1. Resultado da skill de analise (diagnostico/KPI/projecao/dashboard/credito)
2. Entidade(s), periodo e recorte (entidade/grupo/total)
3. Origem dos dados (ofx/csv/xlsx/nfe/manual) e status da conciliacao
4. Fontes oficiais usadas (SGS BCB: ao vivo / cache / indisponivel)
5. Skill geradora

## 3. OS QUATRO GATES

### R1 — INTEGRIDADE DE DADOS

- [ ] **Cobertura** — todos os arquivos/contas do escopo foram lidos?
- [ ] **Buracos de periodo** — ha competencia faltando no intervalo? (ex: extrato de marco ausente)
- [ ] **Conciliacao** — fechou? quantos lancamentos sem nota / notas sem pagamento ficaram pendentes?
- [ ] **Valor sem origem** — todo numero do output rastreia a uma transacao/doc/serie? (nada "do nada")
- [ ] **Dedup** — sem transacao contada 2× (hash canonico §3)?
- [ ] **Vinculo de conta** — toda transacao tem `entidade_id`+`conta_id` validos no grafo?

**Pegadinha R1:** mes faltando vira projecao de fluxo errada com cara de certa → BLOQUEADO ate declarar o buraco.

### R2 — CORRECAO DE CALCULO

- [ ] **Formulas de KPI** conferidas (liquidez, margem, endividamento, ciclo — `config/indicadores.json`)
- [ ] **Series BCB** da **modalidade certa** (`config/series-bcb.json`: capital de giro PJ ≠ credito pessoal PF) e **buscadas ao vivo** (cache com data; nunca chumbado)
- [ ] **Nenhuma taxa/indice fabricado** — fonte indisponivel foi **declarada**, nao estimada (trava 4)
- [ ] **Sinal/competencia** — C/D corretos; transacao na competencia certa
- [ ] **Intragrupo eliminado** nos recortes grupo/total (nao infla receita)
- [ ] **Arredondamento** consistente (2 casas, formato BR 1.234,56)

**Pegadinha R2:** comparar taxa de financiamento de veiculo PF contra serie de capital de giro PJ → comparacao invalida. **Pegadinha R2:** SGS fora do ar e o output "estimou" a media → BLOQUEADO (trava 4).

### R3 — CALIBRAGEM DE CONCLUSAO

- [ ] **Nenhuma afirmacao de ilegalidade** — varrer verbos proibidos (`config/compliance.json` → `credito_verbos_proibidos`: ilegal, abusiva, cabe acao revisional, ajuize, nulidade, e crime...)
- [ ] **Municao rotulada** — credito sai como apontamento comparativo, nunca veredito (trava 1)
- [ ] **Disclaimer de credito** fixo presente em toda saida de credito (`config/compliance.json`)
- [ ] **Gatilho 1,5×** descrito como atencao/negociacao, com STJ REsp 1.061.530/RS — NUNCA como "abusividade comprovada"
- [ ] **Gate de envio** respeitado — nenhuma saida disparou e-mail sem confirmacao (trava 2)
- [ ] **LGPD/mascaramento** — output e log nao expoem conta/CPF/CNPJ completo/saldo em texto plano (trava 3)
- [ ] **Handoff de escopo** — tributario formal e extrajudicial sinalizados como handoff, nao executados

**Pegadinha R3:** "essa taxa esta abusiva, da pra entrar com revisional" → BLOQUEADO. Reescrever como municao + recomendar negociacao + remeter a assessoria.

### R4 — COMPLETUDE E APRESENTACAO

- [ ] **Recortes corretos** — entidade/grupo/total conforme pedido; fronteira **PF↔PJ explicita**
- [ ] **PF e PJ** ambos cobertos quando o escopo era "total" (nada faltou)
- [ ] **Dashboard cobre** os paineis pedidos (resumo, fluxo, aging, credito, margem, seletor de recorte)
- [ ] **Respondeu a pergunta** de fato (ex: "quanto posso gastar" → valor gastavel real, nao saldo bruto)
- [ ] **Provisoes consideradas** quando a pergunta envolve caixa disponivel
- [ ] **Formato BR** — datas DD/MM/AAAA, R$ com 2 casas; aviso de cutoff/validacao presente
- [ ] **Indisponibilidade declarada** no output quando alguma fonte falhou

**Pegadinha R4:** entregar "saldo da conta" quando perguntaram "quanto posso gastar" (ignorando provisoes/AP) → REVISAR.

## 4. OUTPUT — RELATORIO CONSOLIDADO

```markdown
## Auditoria CFO R1-R4

**Entrega auditada:** [tipo + entidade(s) + periodo + recorte]
**Skill geradora:** [nome]

### R1 — INTEGRIDADE DE DADOS
| Item | Status | Observacao |
|------|--------|------------|
| Cobertura de arquivos/contas | ✅/⚠️/🛑 | ... |
| Buracos de periodo | ✅/⚠️/🛑 | ... |
| Conciliacao fechou | ✅/⚠️/🛑 | ... |
| Valor sem origem | ✅/⚠️/🛑 | ... |
**Veredito R1:** ✅ OK / ⚠️ REVISAR / 🛑 BLOQUEADO

### R2 — CORRECAO DE CALCULO
| Item | Status | Observacao |
|------|--------|------------|
| Formulas de KPI | ✅/⚠️/🛑 | ... |
| Serie BCB modalidade certa + ao vivo | ✅/⚠️/🛑 | ... |
| Nenhum numero fabricado | ✅/⚠️/🛑 | ... |
| Intragrupo eliminado | ✅/⚠️/🛑 | ... |
**Veredito R2:** ✅ OK / ⚠️ REVISAR / 🛑 BLOQUEADO

### R3 — CALIBRAGEM DE CONCLUSAO
| Item | Status | Observacao |
|------|--------|------------|
| Sem verbo de ilegalidade | ✅/⚠️/🛑 | ... |
| Municao rotulada | ✅/⚠️/🛑 | ... |
| Disclaimer de credito presente | ✅/⚠️/🛑 | ... |
| Gate de envio respeitado | ✅/⚠️/🛑 | ... |
| LGPD/mascaramento | ✅/⚠️/🛑 | ... |
**Veredito R3:** ✅ OK / ⚠️ REVISAR / 🛑 BLOQUEADO

### R4 — COMPLETUDE E APRESENTACAO
| Item | Status | Observacao |
|------|--------|------------|
| Recortes corretos (entidade/grupo/total) | ✅/⚠️/🛑 | ... |
| PF + PJ cobertos | ✅/⚠️/🛑 | ... |
| Respondeu a pergunta | ✅/⚠️/🛑 | ... |
| Formato BR + aviso de cutoff | ✅/⚠️/🛑 | ... |
**Veredito R4:** ✅ OK / ⚠️ REVISAR / 🛑 BLOQUEADO

---

## VEREDITO CONSOLIDADO

**R1✓/R2✓/R3✓/R4✓ — APROVADO**   (so este libera a entrega)
ou ⚠️ REVISAR — corrigir [N] itens antes de entregar
ou 🛑 RETIDO — corrigir os itens 🛑; saida NAO vai ao gestor

### Recomendacoes especificas
1. ...
```

## 5. AVISOS OBRIGATORIOS NO OUTPUT FINAL

```
⚠️ APOS AUDITORIA R1-R4:
1. APROVADO nao substitui sua revisao — voce e o responsavel ultimo pela decisao financeira.
2. R1-R4 audita coerencia interna + calibragem; nao substitui contador/assessoria em caso complexo.
3. Numeros de mercado tem cutoff da data de extracao da serie SGS — revalide antes de decidir.
4. Diagnostico financeiro nao e parecer juridico nem tributario formal (handoff ao ecossistema).
```

## 6. INTEGRACAO

- **Upstream:** TODAS as skills de analise do plugin (auto-disparada pelo `cfo-master`).
- **Downstream:** se APROVADO, libera a entrega; se REVISAR/RETIDO, retorna a skill geradora para correcao e nova rodada.

## 7. PROIBICOES

1. **NUNCA marcar APROVADO** com ≥1 gate em 🛑.
2. **NUNCA pular a auditoria** — mesmo a pedido; regra dura.
3. **NUNCA "consertar" o numero automaticamente** — sinalizar e devolver a skill geradora.
4. **NUNCA marcar R2 OK** com taxa/indice fabricado ou de modalidade errada.
5. **NUNCA marcar R3 OK** se ha verbo de ilegalidade ou disclaimer de credito ausente.
6. **NUNCA marcar R3 OK** se algum dado sensivel apareceu sem mascaramento.
7. **NUNCA marcar R4 OK** se transferencia intragrupo nao foi eliminada nos recortes grupo/total.
