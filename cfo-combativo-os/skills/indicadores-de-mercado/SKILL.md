---
name: indicadores-de-mercado
description: >
  INDICADORES-DE-MERCADO — CFO senior que contextualiza as contas da
  entidade com os indicadores macro brasileiros, buscados AO VIVO na API
  SGS do Banco Central (NUNCA chumba numero — trava 4): Selic, CDI, IPCA
  e IGP-M. Mede tres coisas que o gestor sente no bolso: (1) custo de
  oportunidade do caixa parado vs Selic/CDI, (2) corrosao inflacionaria
  dos recebiveis a prazo vs IPCA, (3) endividamento da entidade vs custo
  de capital de mercado. Use quando o operador disser "vale a pena
  deixar o caixa parado?", "minha aplicacao rende?", "a inflacao esta
  comendo meu recebivel?", "como esta a Selic / o CDI?", "custo de
  capital", "indicadores de mercado" ou pedir contexto macro das contas.
---

# INDICADORES-DE-MERCADO — Macro x Contas da Entidade

## 1. ESCOPO

Skill de analise (Camada B) que pega os numeros da entidade e os coloca
contra o pano de fundo da economia. Nao e relatorio macro academico —
e CFO traduzindo Selic/CDI/IPCA/IGP-M em **decisao**: deixar o caixa
parado ou aplicar? o recebivel a prazo esta perdendo valor? o
endividamento esta caro frente ao mercado?

## 2. INPUT

| Campo | Origem | Uso |
|---|---|---|
| Saldo em caixa medio | `fluxo-de-caixa` | custo de oportunidade |
| Recebiveis a prazo + prazos | `contas-a-receber` (aging/PMR) | corrosao inflacionaria |
| Divida + taxa media contratada | `analise-credito-bancario` / contratos | custo de capital |
| Recorte multi-entidade | `cfo-state.json` (§2.3) | herdado do `cfo-master` |

## 3. SERIE BCB — BUSCA AO VIVO (NUNCA CHUMBA)

`config/series-bcb.json` → `series.macro`:

| Indicador | codigo SGS | unidade |
|---|---|---|
| Selic meta | 432 | % a.a. |
| CDI diario | 12 | % a.d. |
| IPCA mensal | 433 | % mes |
| IGP-M mensal | 189 | % mes |

**Orquestra `scripts/lib/bcb_client.py`:**
```
python3 scripts/lib/bcb_client.py --serie 432 --ultimos 1     # Selic
python3 scripts/lib/bcb_client.py --serie 433 --ultimos 12    # IPCA 12m
```
- CDI diario (cod 12) → anualizar: `(1+cdi_dia)^252 - 1`.
- IPCA/IGP-M → acumular os ultimos N meses para taxa 12 meses.
- API indisponivel → `bcb_client` retorna indisponivel; a skill
  **declara** (`config/compliance.json` → `indisponibilidade_fonte`) e
  **nao estima** o indice (trava 4 / premortem C3). Sem indice = sem
  conclusao numerica daquele item.

## 4. PROCESSAMENTO

### 4.1 Custo de oportunidade do caixa parado
- `rendimento_potencial_mes = saldo_caixa_medio * (cdi_anual /12)` (ou Selic).
- Comparar com o que o caixa de fato rendeu (se em conta sem remuneracao,
  rendeu ~0). Diferenca = **dinheiro deixado na mesa**.
- Leitura de CFO: caixa operacional precisa de liquidez; mas excedente
  estrutural parado a 0% perde para Selic/CDI todo mes.

### 4.2 Corrosao inflacionaria de recebiveis a prazo
- Recebivel de R$ X a receber em PMR dias perde poder de compra a
  `ipca_periodo`.
- `perda_real_rs ≈ valor_recebivel * (ipca_mensal/30 * PMR_dias)`.
- Leitura: se a venda a prazo nao embute correcao >= IPCA, a margem
  nominal esconde uma margem real menor.

### 4.3 Endividamento vs custo de capital de mercado
- Comparar taxa media da divida da entidade com Selic + CDI (piso de
  mercado) e com a media BCB da modalidade (via `analise-credito-bancario`).
- Leitura: divida a taxa proxima da Selic e barata; muito acima do CDI
  sinaliza custo de capital elevado — cruzar com a analise de credito.

## 5. OUTPUT

```markdown
## 📊 Indicadores de Mercado x {{entidade/grupo/total}} · {{data}}

**Macro (BCB/SGS, {{data_serie}}):** Selic {{selic}}% a.a. · CDI {{cdi_anual}}% a.a. · IPCA 12m {{ipca12}}% · IGP-M 12m {{igpm12}}%
> fonte: Banco Central do Brasil (SGS) — buscado ao vivo

### Custo de oportunidade do caixa
- Caixa medio: R$ {{caixa}} · rendendo ~R$ {{rendeu}}/mes
- Potencial a CDI/Selic: ~R$ {{potencial}}/mes
- 🟡 **Na mesa: ~R$ {{gap}}/mes** se houver excedente estrutural parado.

### Corrosao inflacionaria dos recebiveis
- Recebiveis a prazo: R$ {{ar}} · PMR {{pmr}} dias
- Perda real estimada por IPCA: ~R$ {{perda}}/ciclo
- 🟡 Venda a prazo sem correcao >= IPCA reduz a margem real.

### Endividamento vs mercado
- Taxa media da divida: {{taxa_div}}% a.a. vs CDI {{cdi}}% / Selic {{selic}}%
- 🔴/🟡/🟢 {{leitura}}

### 📝 Recomendacao do CFO
[2-3 acoes: aplicar excedente, embutir correcao no prazo, renegociar divida cara]
```

## 6. RECORTE MULTI-ENTIDADE

No recorte grupo/total, agregar caixa e divida por entidade (apos
eliminar transferencias intragrupo na conciliacao — premortem C7) e
aplicar os indicadores macro sobre o consolidado. Fronteira PF↔PJ
explicita: o custo de oportunidade da PF e da PJ pode ter tratamento
tributario distinto — sinalizar, sem fazer planejamento tributario
(handoff a `tributario-societario-adv-os`).

## 7. INTEGRACAO

### Upstream
- `cfo-master` (roteia pergunta macro)

### Downstream
- `auditoria-cfo` — R2 confere que cada indice tem origem rastreavel
  (BCB/SGS, data); rejeita numero sem fonte.
- `relatorio-executivo` — incorpora a leitura macro no sumario.

### Cross-link
- `analise-credito-bancario` — fornece a taxa media da divida.
- `dashboard-html` — pode exibir os indicadores no resumo executivo.

## 8. PROIBICOES

1. **Nunca** chumbar Selic/CDI/IPCA/IGP-M — sempre buscar ao vivo.
2. **Nunca** estimar indice quando a API SGS estiver fora — declarar.
3. **Nunca** prometer rendimento futuro — apresentar como potencial/cenario.
4. **Nunca** fazer planejamento tributario do excedente — handoff.

## 💡 Proximos passos opcionais

| Proximo passo | Comando |
|---|---|
| Analisar uma taxa de credito | `/cfo-credito` |
| Ver projecao de caixa | `/cfo-caixa` |
| Ver no dashboard | `/cfo-dashboard` |

> Indicadores buscados ao vivo no Banco Central. Validar antes de
> decisao de investimento — este plugin gera dados, nao recomendacao de
> aplicacao financeira.
