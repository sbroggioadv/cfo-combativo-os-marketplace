---
name: dashboard-html
description: >
  DASHBOARD-HTML — Gera o dashboard financeiro como arquivo HTML unico,
  standalone e auto-contido (sem servidor, sem localStorage, dados
  injetados na geracao), na identidade visual canonica do CFO Combativo
  (#101010 base / #CCFF00 acento) com Chart.js. Orquestra
  scripts/lib/dashboard_generator.py a partir do consolidado SQLite.
  Paineis: resumo executivo (KPI cards semaforicos), fluxo de caixa
  (linha + projecao + alerta de ruptura), aging AP/AR, benchmark de
  credito BCB (tabela + disclaimer fixo), saude de margem por produto e
  SELETOR de recorte multi-entidade (entidade/grupo/total). Responsivo,
  pronto para impressao/PDF. Use quando o operador disser "gera o
  dashboard", "quero ver isso visualmente", "painel financeiro",
  "dashboard", "relatorio visual", "exportar PDF do painel" ou rodar
  /cfo-dashboard.
---

# DASHBOARD-HTML — Visualizacao Single-File

## 1. ESCOPO

Camada D (visualizacao). Pega o consolidado da(s) entidade(s) e gera UM
arquivo `.html` que abre em qualquer navegador, sem dependencia de rede
em runtime (alem do CDN do Chart.js, com fallback declarado). O
`dashboard_generator.py` monta o HTML; o
`templates/dashboard-reference.html` e o **fiel de referencia visual** —
qualquer painel novo segue exatamente essa identidade.

**NAO faz:** nao calcula KPI nem busca taxa (isso e das skills de
analise); apenas **renderiza** o que ja foi calculado e auditado.

## 2. INPUT

| Campo | Origem |
|---|---|
| Consolidado por recorte | `consolidacao-multi-entidade` (entidade/grupo/total) |
| KPIs semaforicos | `indicadores-kpi` |
| Serie de fluxo + projecao + ruptura | `fluxo-de-caixa` |
| Aging AP/AR | `contas-a-pagar` / `contas-a-receber` |
| Tabela de credito BCB + disclaimer | `analise-credito-bancario` |
| Saude de margem | `benchmark-precos` |
| Grafo (para o seletor) | `cfo-state.json` |

Dados ausentes → o painel correspondente mostra estado vazio com nota
("sem dados para o periodo"), nunca inventa numeros (trava 4).

## 3. ORQUESTRACAO DO GENERATOR

```
python3 scripts/lib/dashboard_generator.py \
  --consolidado <path do JSON consolidado> \
  --recorte-default total \
  --out <cwd>/.cfo/dashboards/dashboard-{competencia}.html
```
- O generator le o consolidado (montado a partir do SQLite por entidade)
  e injeta os dados **inline** no HTML (sem fetch em runtime).
- **Degradacao graciosa (premortem C2):** se uma lib auxiliar faltar, o
  generator cai para template-string puro de stdlib; nunca quebra a
  sessao. Se o generator nao puder rodar, instruir `pip install` e
  oferecer o HTML montado manualmente a partir do template.
- Saida em `<cwd>/.cfo/dashboards/` — **nunca** versionado (LGPD, §C4).

## 4. IDENTIDADE VISUAL CANONICA

Tokens (de `dashboard-reference.html` — nao alterar):
```
--base:#101010; --surface:#1a1a1a; --surface2:#222; --line:#2e2e2e;
--lime:#CCFF00; --text:#f2f2f2; --muted:#8a8a8a;
--green:#3ddc84; --amber:#ffc043; --red:#ff5252;
```
- Header com brand "CFO Combativo" + borda inferior lime.
- KPI cards com dot semaforico (`.g`/`.a`/`.r`).
- Chart.js 4.x via CDN (`cdn.jsdelivr.net`); nota de fallback offline
  ("graficos exigem conexao na 1a abertura; texto/tabelas funcionam
  offline").
- Responsivo + `@media print` para PDF limpo.
- **Despersonalizado:** rodape NUNCA traz nome civil/OAB — usar marca
  neutra do ecossistema. O exemplo de referencia contem um nome real
  apenas como amostra; o output gerado **nao** o reproduz.

## 5. PAINEIS (design-spec §8)

| Painel | Tipo | Fonte de dado |
|---|---|---|
| Resumo executivo | KPI cards semaforicos | `indicadores-kpi` |
| Fluxo de caixa | linha realizado+projetado + alerta de ruptura | `fluxo-de-caixa` |
| Aging recebiveis | barras semaforicas (a vencer/1-30/31-60/61-90/+90) | `contas-a-receber` |
| Aging pagamentos | barras (a vencer/7d/vencido) | `contas-a-pagar` |
| Analise de credito BCB | tabela contratada x media BCB + **disclaimer fixo** | `analise-credito-bancario` |
| Saude de margem | barras por produto (verde/amarelo/vermelho) | `benchmark-precos` |

O painel de credito **sempre** injeta o `disclaimer_credito_fixo` de
`config/compliance.json` (trava 1) e, no alerta, o texto do semaforo —
nunca verbo de ilegalidade.

## 6. SELETOR DE RECORTE MULTI-ENTIDADE

Controle no topo do dashboard que alterna entre os tres recortes (§2.3):
- **Por entidade** (dropdown com cada entidade do grafo)
- **Por grupo** (intragrupo eliminado)
- **Total consolidado** (subtotais PJ/PF + total)

Os dados dos tres recortes sao **injetados inline na geracao** (sem
servidor); o seletor so troca qual conjunto e exibido via JS local. O
recorte default vem de `preferences.recorte_default` do state.

## 7. OUTPUT

```markdown
## 🖥️ Dashboard gerado

- **Arquivo:** `<cwd>/.cfo/dashboards/dashboard-{{competencia}}.html`
- **Recorte default:** {{total|grupo|entidade}}
- **Paineis incluidos:** resumo, fluxo, aging AP/AR, credito BCB, margem
- **Abra no navegador** (duplo clique) — funciona offline exceto
  graficos na 1a carga.

> Nenhum dado foi transmitido. Arquivo local, fora do git.
> Para PDF: abrir no navegador → Imprimir → Salvar como PDF.
```

## 8. INTEGRACAO

### Upstream
- `cfo-master` (roteia /cfo-dashboard)
- todas as skills de analise (fornecem os dados ja auditados)

### Downstream
- `auditoria-cfo` — R4 confere que os paineis pedidos estao presentes e
  que os recortes batem com a `consolidacao-multi-entidade`; R3 confere
  disclaimer de credito presente.
- `relatorio-executivo` — usa o mesmo dashboard como base do PDF narrado.

## 9. PROIBICOES

1. **Nunca** depender de servidor ou localStorage — single-file inline.
2. **Nunca** inventar numero para preencher painel vazio (trava 4) —
   mostrar estado vazio declarado.
3. **Nunca** alterar a identidade visual canonica (#101010/#CCFF00).
4. **Nunca** renderizar credito sem o disclaimer fixo.
5. **Nunca** gravar o HTML em pasta versionada/sincronizada (LGPD).
6. **Nunca** reproduzir nome civil/OAB no rodape — marca neutra.

## 💡 Proximos passos opcionais

| Proximo passo | Comando |
|---|---|
| Sumario narrado + exportacoes | (relatorio-executivo) |
| Trocar recorte default | `/cfo-setup` |
| Recalcular KPIs antes de gerar | `/cfo-kpi` |

> Dashboard gerado localmente. Validar numeros contra a contabilidade
> antes de uso externo — o plugin gera visualizacao, nao demonstracao
> contabil oficial.
