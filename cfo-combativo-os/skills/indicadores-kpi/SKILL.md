---
name: indicadores-kpi
description: >
  INDICADORES-KPI — Painel completo de KPIs de CFO lendo formulas e faixas
  semaforicas de config/indicadores.json via scripts/lib/kpi_engine.py.
  Cobre LIQUIDEZ (corrente, seca, imediata), ENDIVIDAMENTO (geral, Div.Liq/
  EBITDA, alavancagem, cobertura de juros ICSD), PRAZOS/CICLO (PMR, PMP,
  PME, ciclo financeiro, conversao de caixa), RENTABILIDADE (margens, ROI,
  ROE, ROA, ROIC) e OPERACIONAL (break-even, giros, ticket medio, NCG).
  Cada KPI: valor + semaforo (verde/amarelo/vermelho) + COMENTARIO de CFO
  (o que significa, o que fazer). Suporta os tres recortes multi-entidade.
  Use quando o operador disser "indicadores", "KPIs", "minha liquidez",
  "endividamento", "margens", "ciclo de caixa", "saude financeira",
  "/cfo-kpi". Nunca fabrica numero (trava 4).
---

# INDICADORES-KPI — Painel de KPIs com Leitura de CFO

## 1. ESCOPO

Skill Camada B (Analise) do `cfo-combativo-os`. Monta o **painel de
indicadores financeiros** da entidade: pega os agregados do consolidado,
aplica as **formulas e faixas semaforicas de `config/indicadores.json`**
via `kpi_engine.py`, e devolve cada KPI com **valor + semaforo +
comentario de CFO**. Nao e tabela de numeros — e diagnostico.

**Acionada por:** "indicadores", "KPIs", "minha liquidez",
"endividamento", "margens", "ciclo de caixa", "saude financeira",
`/cfo-kpi`.

**NAO faz:** ingestao, projecao de fluxo (e `fluxo-de-caixa`), parecer
juridico, envio externo.

## 2. AS QUATRO TRAVAS (sempre)

1. **Municao, nunca veredito** — interpreta indicador; nao afirma
   ilegalidade nem dado contabil oficial. O comentario e leitura de
   gestao, nao parecer.
2. **Gate de envio humano** — nao envia nada.
3. **Dado sensivel local** — agregados ficam na maquina; mascarar em log.
4. **Nunca fabricar** — todo input (AC, PC, EBITDA, receita, estoque...)
   vem do consolidado. Faltando uma conta para uma formula → o KPI sai
   **`[indisponivel — falta X]`**, nunca com numero estimado.

## 3. FONTE DE DADOS — ORQUESTRA, NAO REIMPLEMENTA

A matematica dos KPIs **nao vive neste markdown**. A skill:

1. Pede a `scripts/lib/canonical.py` os agregados do recorte/periodo
   (ativo circulante, passivo circulante, disponivel, estoque, receita,
   CMV, EBITDA, lucro liquido, PL, contas a receber/pagar, etc.).
2. Chama `scripts/lib/kpi_engine.py`, que **le `config/indicadores.json`**
   (formulas + faixas), calcula cada indicador e retorna
   `{valor, unidade, semaforo, faixa_aplicada}`.
3. A skill escreve o **comentario de CFO** sobre cada resultado.

O `kpi_engine.py` e a unica fonte das formulas — a skill nunca recalcula
"na mao" nem chumba faixa no texto (evita drift com o config).

## 4. INPUT NECESSARIO

- **Recorte:** entidade / grupo / total.
- **Periodo / data-base** (KPIs de estoque sao pontuais; de fluxo, do
  periodo).
- **Cobertura de dados:** PJ com balanco x PF sem balanco completo. Para
  PF, varios KPIs (PL, EBITDA, estoque) nao se aplicam — a skill seleciona
  o subconjunto pertinente e **declara o que nao roda**.

## 5. GRUPOS DE KPI (de config/indicadores.json)

### Liquidez (capacidade de honrar o curto prazo)
- **Corrente** = AC/PC · verde ≥1,5 / amarelo 1,0-1,49 / vermelho <1,0.
- **Seca** = (AC−Estoque)/PC · verde ≥1,0 / amarelo 0,7-0,99 / vermelho <0,7.
- **Imediata** = Disponivel/PC · verde ≥0,5 / amarelo 0,2-0,49 / vermelho <0,2.

### Endividamento (estrutura e custo da divida)
- **Geral** = Passivo/Ativo · verde <0,5 / amarelo 0,5-0,7 / vermelho >0,7.
- **Divida Liq./EBITDA** · verde <1,5 / amarelo 1,5-3,0 / vermelho >3,0.
- **Alavancagem** = Passivo/PL · verde <1,0 / amarelo 1,0-2,0 / vermelho >2,0.
- **Cobertura de juros (ICSD)** = EBIT/Desp. Financeira · verde ≥3,0 /
  amarelo 1,5-2,99 / vermelho <1,5.

### Prazos / ciclo (em dias — quanto o dinheiro fica parado)
- **PMR** (recebimento), **PMP** (pagamento), **PME** (estoque).
- **Ciclo financeiro** = PMR + PME − PMP (= ciclo de conversao de caixa).
  Menor e melhor; **negativo e otimo** (fornecedor financia a operacao).

### Rentabilidade (% — quanto sobra)
- Margens **bruta / EBITDA / liquida**, **ROI, ROE, ROA, ROIC**.
- O config nao chumba faixa universal de margem (varia por setor) — o
  comentario contextualiza ao porte/setor; nunca rotular como
  "boa/ruim" sem essa ressalva.

### Operacional
- **Ponto de equilibrio (break-even)** em R$, **giro de ativos**,
  **giro de estoque**, **ticket medio**, **NCG** (necessidade de capital
  de giro = (AR + Estoque) − AP).

## 6. PROCESSAMENTO

1. Resolver recorte/periodo e puxar agregados (`canonical.py`).
2. Selecionar o conjunto de KPIs aplicavel (PF poda os que dependem de
   balanco/EBITDA/estoque).
3. Rodar `kpi_engine.py` → valor + semaforo por KPI.
4. Para cada KPI: **comentario de CFO** = (a) o que o numero significa em
   linguagem de gestor, (b) o que fazer se amarelo/vermelho.
5. Fechar com **3-5 prioridades** — os KPIs vermelhos que mais ameacam o
   caixa, em ordem de ataque.
6. KPI sem dado → `[indisponivel — falta X]`, nunca numero estimado.

## 7. OUTPUT — MODELO

```markdown
# Painel de KPIs — [recorte] — [periodo]
**Recorte:** [...]   **Data-base:** [DD/MM/AAAA]   **Tipo:** [PJ / PF]

## Liquidez
| KPI | Valor | Semaforo | Leitura de CFO |
|-----|-------|----------|----------------|
| Corrente | [v] | 🟢/🟡/🔴 | [o que significa + o que fazer] |
| Seca | ... |
| Imediata | ... |

## Endividamento
[mesmo formato: geral, Div.Liq/EBITDA, alavancagem, ICSD]

## Prazos / Ciclo (dias)
[PMR, PMP, PME, ciclo financeiro — leitura de quanto o caixa fica preso]

## Rentabilidade (%)
[margens, ROI/ROE/ROA/ROIC — com ressalva de comparacao setorial]

## Operacional
[break-even, giros, ticket medio, NCG]

## Prioridades do mes (leitura consolidada de CFO)
1. 🔴 [KPI] — [risco + acao]
2. 🟡 [KPI] — [acao preventiva]
...

## Indisponiveis
[KPIs nao calculados e por que — falta de dado / nao aplicavel a PF]
```

## 8. COMENTARIO DE CFO — COMO LER (exemplos do que escrever)

- **Liquidez corrente alta + ciclo financeiro longo:** "tem ativo, mas o
  dinheiro esta preso em estoque/recebivel — folga contabil nao e folga
  de caixa". Atacar PMR e PME.
- **Div.Liq/EBITDA > 3:** "a divida custa mais do que a operacao gera para
  paga-la — alavancagem perigosa; renegociar prazo/custo antes de tomar
  mais credito" (cruza com `analise-credito-bancario`).
- **ICSD < 1,5:** "o resultado operacional mal cobre os juros — qualquer
  tropeco vira inadimplencia".
- **Ciclo financeiro negativo:** "otimo — fornecedor financia a operacao;
  o desafio e manter sem queimar a relacao".
- **NCG crescente:** "o crescimento esta consumindo caixa; vender mais
  esta piorando o caixa, nao melhorando — classico de empresa que cresce
  e quebra".

Sempre dizer **o que significa** e **o que fazer**. Numero sem leitura nao
e KPI de CFO, e planilha.

## 9. PROIBICOES

1. NUNCA recalcular KPI no markdown — `kpi_engine.py` + `indicadores.json`
   sao a unica fonte de formula/faixa.
2. NUNCA chumbar faixa de margem como universal — ressalvar setor/porte.
3. NUNCA exibir KPI sem dado suficiente com numero estimado — marcar
   indisponivel.
4. NUNCA afirmar dado contabil oficial nem ilegalidade — e leitura de
   gestao.
5. NUNCA aplicar a PF os KPIs que dependem de balanco PJ.
6. NUNCA imprimir agregado/valor sensivel em texto plano em log.

## 10. INTEGRACAO

- **Acionada por:** `cfo-master`, `/cfo-kpi`.
- **Aciona em apoio:** `consolidacao-multi-entidade` (recorte),
  `analise-credito-bancario` (quando endividamento aponta custo de divida),
  `indicadores-de-mercado` (custo de capital de mercado vs alavancagem).
- **Encadeia:** `auditoria-cfo` (R1-R4 obrigatoria) e, opcionalmente,
  `dashboard-html` (KPI cards semaforicos).

> Toda saida passa por `auditoria-cfo`. R2 confere as formulas contra
> `config/indicadores.json` e rejeita KPI sem origem; R4 confere o recorte
> e que PF/PJ receberam o conjunto certo.
