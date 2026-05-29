---
name: benchmark-precos
description: >
  BENCHMARK-PRECOS — CFO senior que valida precos vs custo e mercado.
  Cruza margem x custo x preco de venda da tabela de produtos/servicos,
  identifica margem negativa, preco abaixo do break-even e item fora da
  faixa saudavel da categoria. Entrega ranking de saude de margem +
  sugestao de reprecificacao com simulacao de impacto no resultado.
  Pesquisa web de faixa de referencia de mercado SO com autorizacao
  explicita do operador (trava 4 — nunca fabrica numero). Use quando o
  operador disser "esse preco esta certo?", "minha margem aguenta?",
  "estou vendendo no prejuizo?", "quanto cobrar?", "reprecificar",
  "benchmark de preco", "margem por produto" ou rodar /cfo-precos.
---

# BENCHMARK-PRECOS — Saude de Margem e Reprecificacao

## 1. ESCOPO

Skill de analise (Camada B) que responde a pergunta de gestor: **"meus
precos estao saudaveis ou estou queimando margem?"**. Cruza o custo, o
preco de venda e a margem de cada item da tabela de produtos contra o
break-even da operacao e contra a faixa da categoria. Tom: CFO senior —
direto, decisorio, sem rodeio.

**NAO faz:** pesquisa de mercado automatica sem autorizacao; nao promete
resultado de vendas; nao define preco "ideal" como fato — entrega
simulacao e recomendacao para o operador decidir.

## 2. INPUT

| Campo | Origem | Obrigatorio |
|---|---|---|
| Tabela de produtos | `ingest-tabela-produtos` → `{sku, descricao, custo, preco_venda, margem, categoria}` | sim |
| Custos fixos do periodo | `fluxo-de-caixa` / lancamentos conciliados | desejavel (para break-even) |
| Volume por item | tabela ou estimativa do operador | opcional |
| Recorte multi-entidade | `cfo-state.json` (entidade/grupo/total — design-spec §2.3) | herdado do `cfo-master` |

Se faltar `custo` ou `preco_venda` de um item → **pergunta antes de
supor** (PA-14). Nunca calcula margem com custo presumido.

## 3. PROCESSAMENTO

### Passo 1 — Margem unitaria por item
- `margem_bruta_rs = preco_venda - custo`
- `margem_bruta_pct = (preco_venda - custo) / preco_venda`
- Se `custo` inclui so direto, anotar que despesa fixa rateada ainda
  nao entrou (margem de contribuicao ≠ lucro liquido — explicitar).

### Passo 2 — Break-even da operacao
Se ha custos fixos do periodo:
- `ponto_equilibrio_rs = Custos Fixos / (1 - (Custos Variaveis / Receita))`
  (formula em `config/indicadores.json` → `operacional.ponto_equilibrio`).
- Item cujo preco nao cobre custo variavel + parcela de fixo →
  **abaixo do break-even**.

### Passo 3 — Classificacao semaforica por item
| Condicao | Sinal | Rotulo |
|---|---|---|
| margem negativa (`preco_venda < custo`) | 🔴 | vende no prejuizo |
| margem positiva mas abaixo do break-even | 🔴 | nao cobre operacao |
| margem dentro da faixa da categoria | 🟢 | saudavel |
| margem positiva, fora da faixa (muito baixa) | 🟡 | apertada |
| margem muito acima da faixa | 🟡 | revisar (risco de perda de volume / oportunidade) |

A "faixa da categoria" so e afirmada como **referencia de mercado** se o
operador autorizar a pesquisa (Passo 4). Sem isso, a faixa e a do
proprio portfolio (mediana das margens da mesma categoria na tabela) —
rotulada como **referencia interna**, nao de mercado.

### Passo 4 — Faixa de mercado (SO com autorizacao)
Antes de qualquer busca web, perguntar:
> "Para comparar com a faixa de mercado da categoria, preciso pesquisar
> referencias publicas na web. Autoriza a busca agora? (s/n)"
- **Sem autorizacao** → usar so referencia interna; declarar isso no
  output ("faixa de mercado nao pesquisada — comparacao interna").
- **Com autorizacao** → WebSearch/WebFetch da faixa de margem tipica da
  categoria; citar a fonte e a data. Se a busca falhar → declarar a
  indisponibilidade (`config/compliance.json` → `indisponibilidade_fonte`),
  **nunca estimar a faixa como fato** (trava 4).

### Passo 5 — Ranking de saude de margem
Ordenar itens do pior ao melhor por: (1) negativos primeiro, (2) abaixo
do break-even, (3) margem crescente. Topo do ranking = onde o CFO age
primeiro.

### Passo 6 — Simulacao de reprecificacao
Para cada item 🔴/🟡, simular reajuste que leva a margem ao alvo:
- `preco_alvo = custo / (1 - margem_alvo)`
- `delta_preco_pct = (preco_alvo - preco_venda) / preco_venda`
- `impacto_resultado_rs = delta_preco_rs * volume` (se volume conhecido)
- Sinalizar risco de volume: reajuste alto pode reduzir demanda —
  **nao prometer** que o volume se mantem; apresentar como cenario.

## 4. OUTPUT

```markdown
## 💹 Benchmark de Precos — {{entidade/grupo/total}} · {{competencia}}

**Base de comparacao:** [referencia interna | mercado pesquisado em DD/MM, fonte: ...]
**Break-even da operacao:** R$ {{ponto_equilibrio}} / periodo

### Ranking de Saude de Margem (pior → melhor)

| # | Item | Custo | Preco | Margem % | vs faixa | Sinal |
|--:|---|---:|---:|---:|:---:|:---:|
| 1 | Servico Express | R$ 52,00 | R$ 50,00 | −4,0% | abaixo | 🔴 prejuizo |
| 2 | Kit D | R$ 92,00 | R$ 100,00 | +8,0% | abaixo | 🟡 apertada |
| 3 | Produto C | R$ 81,00 | R$ 100,00 | +19,0% | dentro | 🟢 |
| ... | | | | | | |

### 🔴 Itens criticos

#### Servico Express — vende no prejuizo (−4%)
- Cada venda **subtrai** R$ 2,00 da operacao antes de qualquer fixo.
- **Simulacao:** preco-alvo p/ margem 12% = R$ 59,09 (+18,2%).
  Recupera ~R$ {{impacto}} / mes ao volume atual.
- ⚠️ Reajuste de +18% pode pressionar volume — apresentar como cenario,
  validar elasticidade com o operador.

### 📝 Recomendacao do CFO

[as 2-3 acoes em ordem: reprecificar X, revisar custo de Y, descontinuar Z se persistir prejuizo]

> Margem de contribuicao ≠ lucro liquido. Rateio de despesa fixa pode
> mudar o quadro — cruzar com `indicadores-kpi` (margem liquida) antes
> de decisao final.
```

## 5. RECORTE MULTI-ENTIDADE

A tabela de produtos pertence a uma entidade. No recorte **grupo/total**,
agregar margens por entidade lado a lado (nao somar precos de entidades
diferentes — sem sentido). Sempre indicar de qual entidade e cada item.

## 6. INTEGRACAO

### Upstream
- `cfo-master` (roteia "/cfo-precos" ou pergunta de preco)
- `ingest-tabela-produtos` (fornece a tabela)

### Downstream
- `auditoria-cfo` — R1-R4 antes do output (R2 confere as formulas; R4 a
  completude do ranking)
- `relatorio-executivo` — narra a recomendacao no sumario mensal

### Cross-link (sugestao, nao execucao)
- `dashboard-html` — painel "Saude de Margem por Produto"
- `tributario-societario-adv-os` — impacto tributario de reprecificacao

## 7. PROIBICOES

1. **Nunca** afirmar faixa de mercado sem pesquisa autorizada e fonte.
2. **Nunca** calcular margem com custo presumido — perguntar.
3. **Nunca** prometer que o reajuste mantem o volume — e cenario.
4. **Nunca** somar precos de entidades distintas no recorte grupo/total.
5. **Nunca** apresentar margem de contribuicao como se fosse lucro
   liquido sem ressalvar o rateio de fixo.

## 💡 Proximos passos opcionais

| Proximo passo | Comando |
|---|---|
| Ver no dashboard | `/cfo-dashboard` |
| Cruzar com margem liquida | `/cfo-kpi` |
| Impacto no caixa | `/cfo-caixa` |

> Validar custos contra a contabilidade antes de decisao de preco final.
