---
name: relatorio-executivo
description: >
  RELATORIO-EXECUTIVO — O dashboard MOSTRA; esta skill EXPLICA e
  RECOMENDA. Produz um sumario narrado em linguagem de CFO senior: as
  3 a 5 coisas que REALMENTE importam no mes, o que fazer sobre cada
  uma, em que ORDEM e com que URGENCIA. Consolida os achados das demais
  skills (caixa, provisoes, orcamento, anomalias, KPIs, credito) numa
  narrativa decisoria. Gera EXPORTACOES: PDF (do dashboard), XLSX
  (consolidado para a contabilidade) e o pacote de triagem. Tambem
  ajuda o operador a CRIAR METAS de poupanca/investimento (gravando em
  metas[] do cfo-state.json) e responde a pergunta classica QUANTO
  POSSO GASTAR ESTE MES (caixa livre apos provisoes e contas a pagar).
  Use quando o operador pedir resumo do mes, relatorio executivo, o que
  e mais importante agora, o que faco primeiro, exportar PDF/XLSX,
  criar meta de poupanca/investimento, ou quanto posso gastar este mes.
---

# RELATORIO-EXECUTIVO — Narrativa de CFO + Exportações

> Camada F · CFO senior, direto e decisório. Quatro travas ativas.
> DESPERSONALIZADO. Sem prometer resultado. Sem afirmar ilegalidade.

## 1. ESCOPO

Camada de **síntese e decisão**. Não recalcula — colhe os outputs já
auditados das outras skills e os transforma em (a) narrativa priorizada,
(b) exportações, (c) metas, (d) resposta de "quanto posso gastar".
Funciona PJ e PF, em qualquer recorte (entidade/grupo/total).

## 2. INPUT
- Entidade(s) + período + recorte.
- Outputs disponíveis de: `fluxo-de-caixa`, `provisoes`, `orcamento`,
  `deteccao-anomalias`, `indicadores-kpi`, `analise-credito-bancario`/
  `capacidade-credito`. Faltando algum → narrar com o que há e declarar
  o que faltou (não preencher buraco com suposição — trava 4).

## 3. PROCESSAMENTO

### 3.1 As 3-5 coisas que importam (priorização)
Ranquear os achados por **impacto em R$ × urgência**:
```
prioridade = impacto_financeiro × peso_urgencia
peso: ruptura de caixa iminente > provisão descoberta > estouro de
      orçamento > anomalia recuperável > KPI fora da faixa
```
Cada item vira um parágrafo curto: **o quê**, **por quê importa**,
**o que fazer**, **prazo**. Tom de CFO — sem rodeios, sem jargão vazio.
Máximo 5 itens (foco; o resto vai no dashboard).

### 3.2 "Quanto posso gastar este mês"
```
gasto_livre = caixa_atual
            − contas a pagar do período (de contas-a-pagar)
            − provisões devidas do período (de provisoes)
            − metas de poupança/investimento do mês (de metas[])
```
Resultado < 0 → 🔴 "não há folga este mês; o caixa já está comprometido
em R$ ___". Mostrar a conta aberta (transparência), nunca só o número.

### 3.3 Criar meta de poupança/investimento
Grava em `metas[]` do `cfo-state.json` via `state.py`:
```json
{"id":"meta-reserva-2026","tipo":"poupanca","entidade_id":"joao",
 "objetivo":"Reserva de emergência 6 meses","valor_alvo":60000.00,
 "prazo":"2026-12","aporte_mensal_sugerido":5000.00,"criado_em":"iso"}
```
Calcular o aporte mensal: `valor_alvo / meses_até_prazo`. Confrontar com
o gasto livre (§3.2) → a meta cabe no caixa? Se o aporte > gasto livre,
avisar e sugerir alongar prazo ou reduzir alvo. Append-only (§2.4) —
não apaga outras metas.

### 3.4 Exportações
- **PDF:** renderiza o dashboard (`dashboard-html` → impressão/PDF).
- **XLSX:** consolidado por competência para a contabilidade (via
  `pandas`/`openpyxl`; fallback CSV se a lib faltar — degradação
  graciosa, premortem C2).
- **Pacote de triagem:** delega a `triagem-contabil` (não duplica).
- Envio externo do pacote → **somente** `envio-contabilidade` com gate
  humano (trava 2). Esta skill **não envia** — só prepara/aponta.

## 4. OUTPUT

```markdown
## Relatório executivo — [entidade/recorte] · [competência]

### As coisas que importam agora
1. **[título]** — [o quê + por quê]. → **Ação:** [o que fazer]. Prazo: __.
2. ...
(até 5)

### Quanto você pode gastar este mês
| Item | Valor |
|---|---|
| Caixa atual | R$ ___ |
| (−) Contas a pagar do período | R$ ___ |
| (−) Provisões devidas | R$ ___ |
| (−) Aporte de metas | R$ ___ |
| **= Gasto livre** | **R$ ___** [🟢/🟡/🔴] |

### Metas
[meta(s) criada(s)/em curso: alvo, prazo, aporte mensal, cabe no caixa?]

### Exportações geradas
- [ ] PDF do dashboard → caminho
- [ ] XLSX consolidado → caminho
- [ ] Pacote de triagem → (via triagem-contabil)
```

## 5. AUDITORIA-CFO
R1 (outputs-fonte presentes? o que faltou foi declarado?), R2 (conta de
gasto livre e aporte conferidos; nada fabricado), R3 (sem veredito
jurídico; nenhum envio disparado aqui — gate respeitado; LGPD/
mascaramento nas exportações), R4 (3-5 prioridades + gasto livre + metas
+ exportações; recorte correto; PF e PJ tratados).

## 6. INTEGRAÇÃO
Topo da cadeia analítica: consome as demais skills da camada B/F, lê/grava
`metas[]`, delega exportação/triagem/envio (não reimplementa). Chamada
tipicamente ao fim de `cfo-master` / `/cfo-full`.

## 7. PROIBIÇÕES
1. **NUNCA** enviar nada externamente — preparar e apontar; envio é do
   `envio-contabilidade` com gate humano (trava 2).
2. **NUNCA** mostrar "quanto posso gastar" sem abater AP + provisões +
   aportes de meta — e sempre exibir a conta aberta.
3. **NUNCA** criar meta cujo aporte não cabe sem avisar (sugerir ajustar
   prazo/alvo).
4. **NUNCA** preencher achado ausente com suposição — declarar o que faltou.
5. **NUNCA** afirmar ilegalidade ao narrar o módulo de crédito.
6. **NUNCA** estourar 5 itens de prioridade — foco é o produto.
