---
name: fluxo-de-caixa
description: >
  FLUXO-DE-CAIXA — Caixa realizado (extratos conciliados) + projetado
  (contas a pagar e a receber agendadas), com ALERTA DE RUPTURA (data
  provavel de saldo negativo) e leitura de sazonalidade vs mesmo periodo
  do ano anterior. Responde "quanto posso gastar este mes" = caixa livre
  apos provisoes + AP do periodo. Suporta os tres recortes multi-entidade
  (entidade / grupo / total). Use quando o operador disser "fluxo de
  caixa", "meu caixa aguenta", "quanto posso gastar este mes", "vou
  ficar no vermelho?", "projecao de saldo", "/cfo-caixa". Le o
  consolidado via scripts/lib/canonical.py e nunca fabrica numero
  (trava 4) — fonte indisponivel e declarada, nao estimada.
---

# FLUXO-DE-CAIXA — Realizado + Projetado + Ruptura

## 1. ESCOPO

Skill Camada B (Analise) do `cfo-combativo-os`. Constroi a visao de
**fluxo de caixa** de uma ou mais entidades: o que ja entrou e saiu
(realizado, dos extratos conciliados) e o que esta agendado para entrar
e sair (projetado, de AP + AR). Produz o **alerta de ruptura** — a data
provavel em que o saldo cruza zero — e a leitura de **sazonalidade**
contra o mesmo periodo do ano anterior.

**Acionada por:** "fluxo de caixa", "meu caixa aguenta junho?", "quanto
posso gastar este mes?", "projecao de saldo", `/cfo-caixa`.

**NAO faz:** ingestao (Camada A), envio externo (gate), parecer
juridico. Apenas le o consolidado e interpreta.

## 2. AS QUATRO TRAVAS (sempre)

1. **Municao, nunca veredito** — aqui se aplica a leitura, nao a
   acusacao. Aponta risco de ruptura; nao afirma insolvencia juridica.
2. **Gate de envio humano** — esta skill nao envia nada. Se o operador
   pedir mandar a projecao a terceiro, encaminhe a `envio-contabilidade`.
3. **Dado sensivel local** — saldos, contas e contrapartes ficam na
   maquina. Em log, mascarar conta/saldo (`mascarar_em_log=true`).
4. **Nunca fabricar** — todo valor vem do SQLite consolidado. Sem dado de
   um periodo → declara o buraco, nao interpola um numero plausivel.

## 3. FONTE DE DADOS — ORQUESTRA, NAO REIMPLEMENTA

A matematica do caixa vive em Python; a skill **chama e interpreta**:

- `scripts/lib/canonical.py` — le o consolidado SQLite (`base.sqlite`
  por entidade), normaliza ao schema canonico (design-spec §3), aplica o
  recorte (entidade/grupo/total) e **elimina transferencias
  intragrupo** (`is_transferencia_intragrupo`) nos recortes grupo/total.
- `scripts/lib/kpi_engine.py` — series temporais de saldo, projecao de
  saldo futuro e deteccao do ponto de cruzamento (ruptura).

A skill **nao soma extrato no markdown**. Pede o numero ao engine, le o
resultado e escreve o **comentario de CFO** sobre ele.

## 4. INPUT NECESSARIO

Antes de iniciar, confirmar (e parar se faltar — nao supor):

- **Recorte:** uma entidade, um grupo, ou total consolidado? (default:
  `preferences.recorte_default` do `cfo-state.json`).
- **Periodo:** mes corrente, proximos N dias, ou intervalo explicito.
- **Conciliacao fechou?** Se ha extrato nao conciliado, o realizado tem
  buraco — sinalizar antes de projetar.
- **AP/AR carregados?** A projecao depende de `contas-a-pagar` e
  `contas-a-receber` estarem alimentados. Sem eles, projeta so com o que
  houver e **declara a limitacao**.

## 5. PROCESSAMENTO — 6 PASSOS

### Passo 1 — Saldo de partida
Saldo atual conciliado do recorte (soma das contas). Se uma conta nao
fechou conciliacao, marcar `[saldo parcial — conta X pendente]`.

### Passo 2 — Realizado do periodo
Entradas e saidas ja ocorridas, por dia/semana/mes (granularidade pedida).
Engine retorna a serie; a skill agrupa por categoria (receita, custo,
despesa fixa/variavel, tributo, financeiro).

### Passo 3 — Projetado
Sobrepor os agendados:
- **A receber** (AR com vencimento dentro do horizonte) — entrada.
- **A pagar** (AP com vencimento dentro do horizonte) — saida.
- Recorrencias conhecidas (assinaturas, folha, tributos a vencer).

Projecao e **deterministica sobre o agendado**, nao previsao estatistica.
Nao inventar receita futura nao agendada.

### Passo 4 — Alerta de ruptura
Engine projeta o saldo dia a dia (partida + entradas − saidas
acumuladas). Identifica a **primeira data em que o saldo fica negativo**.

| Resultado | Leitura |
|-----------|---------|
| Sem cruzamento no horizonte | Caixa cobre o periodo projetado. |
| Cruzamento em > 30 dias | Ruptura no radar; ha margem de manobra. |
| Cruzamento em <= 30 dias | **Ruptura iminente** — priorizar AR e/ou renegociar AP. |
| Cruzamento em <= 7 dias | **Critico** — acao imediata (antecipar recebivel, adiar pagavel nao essencial). |

A ruptura e **alerta**, nao sentenca: depende dos agendados conhecidos.

### Passo 5 — Sazonalidade vs ano anterior
Comparar receita/despesa/saldo do periodo com o **mesmo periodo do ano
anterior** (historico SQLite). Sem 12+ meses de historico → declara:
`[sem base comparavel — historico < 1 ano]`. Nao extrapolar tendencia
de poucos meses como se fosse sazonal.

### Passo 6 — "Quanto posso gastar este mes"
**Caixa livre** = saldo de partida + AR confirmado do mes − AP do mes −
**provisoes devidas** do periodo (chamar `provisoes` para o que deveria
estar reservado: 13o, ferias, tributos a vencer, reserva PF). Responder
com o numero **liquido de provisoes**, nunca o saldo bruto — esse e o
erro classico que estoura o caixa no mes seguinte.

## 6. OUTPUT — MODELO

```markdown
# Fluxo de Caixa — [recorte] — [periodo]
**Recorte:** [entidade / grupo / total]   **Data-base:** [DD/MM/AAAA]

## Posicao
- Saldo de partida (conciliado): R$ [valor]
- Realizado no periodo: entradas R$ [x] / saidas R$ [y] / liquido R$ [z]
- Projetado (AP+AR agendados): entradas R$ [a] / saidas R$ [b]

## Alerta de ruptura
[Sem cruzamento no horizonte de N dias]  — OU —
**Saldo provavel negativo em DD/MM/AAAA** (R$ -[valor]).
Comentario CFO: [causa: concentracao de AP em data X / AR atrasado / ...].
Acao sugerida: [antecipar recebivel Y / renegociar pagavel Z].

## Sazonalidade
[periodo atual] vs [mesmo periodo ano anterior]:
receita [+/- %], despesa [+/- %], saldo [+/- %].
Comentario CFO: [o que mudou e por que importa].

## Quanto posso gastar este mes
Caixa livre apos provisoes + AP do periodo: **R$ [valor]**.
Composicao: partida [x] + AR confirmado [y] − AP [z] − provisoes [w].
Comentario CFO: [margem de seguranca / o que NAO contar como gastavel].

## Limitacoes desta leitura
[conciliacao pendente / AP-AR incompletos / historico < 1 ano — o que
afeta a confiabilidade]
```

## 7. COMENTARIO DE CFO — COMO LER CADA NUMERO

- **Saldo de partida alto, mas ruptura em 15 dias:** o problema nao e
  quanto tem, e o *timing* — concentracao de saidas. Esse e o diagnostico
  que separa CFO de planilha.
- **Caixa livre << saldo bruto:** as provisoes estao comendo o que parece
  disponivel. Gastar o bruto e financiar o 13o/tributo com o caixa do
  proximo mes.
- **Sazonalidade negativa recorrente:** se todo [mes] cai, isso e
  previsivel → vira provisao, nao surpresa.

## 8. PROIBICOES

1. NUNCA somar/projetar numero que nao venha do engine sobre o
   consolidado real.
2. NUNCA tratar saldo bruto como "quanto pode gastar" — sempre liquido
   de provisoes + AP.
3. NUNCA estimar receita futura nao agendada como entrada certa.
4. NUNCA afirmar insolvencia/inadimplencia em termos juridicos — e
   alerta de caixa, nao parecer.
5. NUNCA omitir o bloco "Limitacoes" quando ha buraco de dado.
6. NUNCA imprimir saldo/conta em texto plano em log.

## 9. INTEGRACAO

- **Acionada por:** `cfo-master`, `/cfo-caixa`.
- **Aciona em apoio:** `provisoes` (caixa livre), `contas-a-pagar` e
  `contas-a-receber` (projecao), `consolidacao-multi-entidade` (recorte).
- **Encadeia:** `auditoria-cfo` (R1-R4 obrigatoria antes da entrega) e,
  opcionalmente, `dashboard-html` (painel de fluxo com projecao+ruptura).

> Toda saida passa por `auditoria-cfo`. R2 rejeita numero sem origem
> rastreavel; R4 confere se o recorte pedido foi o entregue.
