---
name: capacidade-credito
description: >
  CAPACIDADE-CREDITO — Complementa o modulo de credito (analise-credito-
  bancario) olhando para FRENTE. Calcula a capacidade de endividamento
  SAUDAVEL da entidade (a partir da geracao de caixa e da cobertura de
  juros — ICSD), SIMULA o impacto de um NOVO emprestimo no fluxo de
  caixa e nos KPIs ANTES da contratacao (e a parcela cabe? a cobertura
  de juros aguenta? o caixa rompe?), e compara propostas de credito pelo
  CET (Custo Efetivo Total — nao so a taxa nominal), confrontando com a
  regua de mercado do BCB (busca ao vivo via series SGS). Mesmas travas
  do modulo de credito: gera MUNICAO comparativa, NUNCA veredito de
  abusividade nem indicacao de acao. Use quando o operador perguntar
  quanto de divida aguento, esse emprestimo cabe no caixa, simular novo
  financiamento, comparar propostas de banco, qual proposta e melhor por
  CET, ou minha capacidade de credito.
---

# CAPACIDADE-CREDITO — Endividamento Saudável e Simulação

> Camada F · CFO senior. **Mesmas 4 travas do módulo de crédito** —
> trava 1 (munição, nunca veredito) vale integralmente aqui.
> DESPERSONALIZADO. Disclaimer fixo de crédito em toda saída.

## 1. ESCOPO

`analise-credito-bancario` olha o crédito que JÁ existe; esta skill olha
o crédito que o operador **pensa em tomar**. Responde: cabe? quanto cabe?
qual proposta custa menos de verdade (CET)? Decisão é do operador — a
skill dá munição, não veredito (trava 1).

## 2. INPUT
- Entidade + recorte + dados do(s) novo(s) empréstimo(s) cogitado(s):
  valor, prazo, taxa nominal (a.m./a.a.), modalidade, e — se houver —
  o **CET** informado pela proposta, mais tarifas/seguros/IOF.
- Geração de caixa e KPIs atuais (de `fluxo-de-caixa` / `indicadores-kpi`).
- Taxa média de mercado da modalidade: **busca ao vivo** na API SGS
  (`config/series-bcb.json`) — **NUNCA chumba número** (premortem C3).
  Indisponível → declara (trava 4), não estima.

## 3. PROCESSAMENTO

### 3.1 Capacidade de endividamento saudável
A partir da geração de caixa recorrente:
```
caixa_operacional_mensal = receita recorrente − custos/despesas recorrentes
margem_para_servico_divida = caixa_operacional × fator_prudencial (default 30%)
```
- Capacidade = parcela máxima que cabe sem comprometer a operação.
- Conferir **cobertura de juros (ICSD)** atual e projetada:
  `ICSD = EBIT (ou caixa operacional) / despesa de juros`. ICSD < 1,5 →
  sinalizar que há pouco fôlego para nova dívida.
- PF: usar comprometimento de renda (parcela / renda líquida; faixa de
  atenção usual ~30%, declarar como referência, não regra legal).

### 3.2 Simulação do novo empréstimo (ANTES de contratar)
Calcular a parcela (Price ou SAC conforme informado):
```
Price: PMT = PV × i / (1 − (1+i)^-n)
SAC:   amortização constante + juros sobre saldo decrescente
```
Projetar no fluxo de caixa: somar a parcela aos AP futuros e reprojetar
saldo → **a nova parcela antecipa/causa ruptura de caixa?** Reapresentar
os KPIs **com** a nova dívida (endividamento geral, Dívida Líq./EBITDA,
ICSD) lado a lado com o cenário atual. Veredito de cabimento financeiro
(cabe / aperta / não cabe) — **cabimento financeiro, não jurídico**.

### 3.3 Comparar propostas por CET (não só taxa nominal)
Taxa nominal engana — comparar **CET**, que embute tarifas, seguros, IOF
e a periodicidade real:
```
Se a proposta informa CET → usar o informado.
Se não → estimar CET a partir de (taxa + tarifas + seguros + IOF) e
ROTULAR como estimativa, instruindo conferir o CET oficial do contrato.
```
Tabela: cada proposta com taxa nominal, **CET**, parcela, total pago,
total de juros. Ordenar por CET. Confrontar com a média BCB (régua) e
aplicar o semáforo calibrado juridicamente (§3.4).

### 3.4 Semáforo (idêntico ao módulo de crédito — `config/compliance.json`)
- Dentro da média → patamar de mercado.
- Acima mas < 1,5× → espaço para negociação; superar a média **NÃO** é
  abusividade (STJ REsp 1.061.530/RS).
- ≥ 1,5× → discrepância relevante; recomenda reunião com o gerente e,
  persistindo, **assessoria especializada**; apontamento comparativo,
  **não** afirmação de ilegalidade.

## 4. OUTPUT

```markdown
## Capacidade de crédito — [entidade] · simulação

### Capacidade saudável
| Indicador | Atual |
|---|---|
| Caixa operacional mensal | R$ ___ |
| Parcela máxima prudencial (30%) | R$ ___ |
| ICSD atual | ___ x |

### Simulação do novo empréstimo
| KPI | Hoje | Com a nova dívida |
|---|---|---|
| Parcela mensal | — | R$ ___ |
| Dívida Líq./EBITDA | ___ | ___ |
| ICSD | ___ | ___ |
| Caixa projetado | ... | ⚠️ ruptura em DD/MM? |
Cabimento financeiro: [cabe / aperta / não cabe] — decisão do operador.

### Comparação de propostas (ordenado por CET)
| Proposta | Taxa nom. | **CET** | Parcela | Total juros | vs média BCB |
|---|---|---|---|---|---|
| A | __% | **__%** | R$ ___ | R$ ___ | 🟢/🟡/🔴 |

> [disclaimer_credito_fixo de config/compliance.json — sempre]
```

## 5. AUDITORIA-CFO
R1 (geração de caixa e KPIs com origem? dados das propostas completos?),
R2 (parcela/CET/projeção conferidos; média BCB ao vivo, nunca chumbada;
indisponibilidade declarada), R3 (**verbos proibidos ausentes**:
ilegal/abusiva/cabe ação/ajuíze; disclaimer presente; munição rotulada;
CET estimado rotulado), R4 (capacidade + simulação + comparação CET
completas; recorte ok).

## 6. INTEGRAÇÃO / HANDOFF
Consome `fluxo-de-caixa` e `indicadores-kpi`; usa `bcb_client.py` (SGS).
Par com `analise-credito-bancario`.

| Próximo passo | Comando | Plugin |
|---|---|---|
| Discussão revisional de contrato | (assessoria jurídica especializada) | — |

## 7. PROIBIÇÕES
1. **NUNCA** afirmar "taxa abusiva/ilegal", "cabe ação", "ajuíze",
   "nulidade" (verbos proibidos — `config/compliance.json`).
2. **NUNCA** chumbar a taxa média de mercado — buscar ao vivo no SGS;
   indisponível → declarar (trava 4).
3. **NUNCA** comparar propostas só pela taxa nominal — o eixo é o **CET**.
4. **NUNCA** apresentar CET estimado como oficial — rotular e instruir
   conferir o contrato.
5. **NUNCA** omitir o disclaimer de crédito.
6. Cabimento aqui é **financeiro**, jamais parecer jurídico.
