---
name: contas-a-receber
description: >
  CONTAS-A-RECEBER — Gestao de AR. Aging (a vencer / 1-30 / 31-60 / 61-90
  / +90 dias), RANKING de inadimplentes por valor x dias de atraso, e fila
  de cobranca priorizada. Suporta os tres recortes multi-entidade
  (entidade / grupo / total). HANDOFF: casos que justificam notificacao
  extrajudicial ou cobranca judicial sao sinalizados ao modulo juridico do
  ecossistema (este plugin sinaliza, NAO produz a peca). Use quando o
  operador disser "contas a receber", "quem me deve", "aging de
  recebiveis", "inadimplentes", "fila de cobranca", "/cfo-receber". Le o
  consolidado via scripts/lib/canonical.py, nunca fabrica numero (trava 4).
---

# CONTAS-A-RECEBER — Aging, Inadimplentes e Fila de Cobranca

## 1. ESCOPO

Skill Camada B (Analise) do `cfo-combativo-os`. Organiza o **ativo a
receber** — quem deve, quanto, e ha quanto tempo. Tres entregas:
(1) **aging** por faixa de atraso, (2) **ranking de inadimplentes** por
severidade (valor x dias), e (3) **fila de cobranca** priorizada. Onde a
inadimplencia escala, faz **handoff** ao modulo juridico — sem produzir
a peca.

**Acionada por:** "contas a receber", "quem me deve", "aging de
recebiveis", "inadimplentes", "fila de cobranca", `/cfo-receber`.

**NAO faz:** produzir notificacao extrajudicial nem peca de cobranca
judicial (handoff), executar cobranca, ingestao, envio externo.

## 2. AS QUATRO TRAVAS (sempre)

1. **Municao, nunca veredito** — sinaliza atraso e prioridade de
   cobranca; nao afirma que o devedor "esta em mora juridica" nem que
   "cabe acao". Quem qualifica juridicamente e o advogado (handoff §5).
2. **Gate de envio humano** — esta skill nao dispara cobranca a ninguem.
   So organiza a fila.
3. **Dado sensivel local** — clientes/devedores, valores e contatos ficam
   na maquina; mascarar em log.
4. **Nunca fabricar** — valores e datas de vencimento vem do consolidado.
   Recebivel sem vencimento → sinaliza pendencia, nao inventa.

## 3. FONTE DE DADOS — ORQUESTRA, NAO REIMPLEMENTA

- `scripts/lib/canonical.py` — le o consolidado SQLite, aplica o recorte e
  elimina transferencias intragrupo (recebivel "de outra entidade do
  mesmo grupo" nao e AR real do consolidado — e movimento interno).
- `scripts/lib/kpi_engine.py` — buckets de aging, score de severidade
  (valor x dias) e ordenacao da fila de cobranca.

A skill **nao calcula o aging no markdown** — pede ao engine e escreve o
comentario sobre o resultado.

## 4. INPUT NECESSARIO

- **Recorte:** entidade / grupo / total.
- **Data-base** do aging (default: hoje).
- **Politica de cobranca** (opcional): a partir de quantos dias o operador
  considera escalar (lembrete → cobranca formal → handoff juridico).
- **Contatos** dos devedores (opcional): so para montar a fila; nunca
  para disparo automatico.

## 5. PROCESSAMENTO

### Passo 1 — Aging por faixa
Distribuir os recebiveis em buckets (faixas canonicas):

| Faixa | Leitura |
|-------|---------|
| **A vencer** | saudavel — ainda no prazo |
| **1-30 dias** | atraso recente — lembrete suave costuma resolver |
| **31-60 dias** | atraso consolidado — cobranca ativa |
| **61-90 dias** | risco crescente — cobranca formal |
| **+90 dias** | risco alto de perda — avaliar provisao p/ devedores duvidosos + handoff |

Engine retorna o total e a contagem por faixa.

### Passo 2 — Ranking de inadimplentes (valor x dias)
Ranquear devedores por **severidade = valor em atraso ponderado por dias
de atraso**. Um devedor de R$ 50k ha 90 dias pesa mais que dez de R$ 2k
ha 15. O engine calcula o score; a skill lista do mais ao menos critico,
com valor, faixa e dias.

### Passo 3 — Fila de cobranca
Para cada devedor, sugerir o **nivel de acao** conforme dias/valor e a
politica do operador:

- 1-30 dias → lembrete amigavel.
- 31-60 → cobranca ativa (contato direto, proposta de parcelamento).
- 61-90 → cobranca formal documentada.
- +90 ou valor alto persistente → **handoff juridico** (§abaixo).

A fila e **sugestao operacional de gestao de caixa**, nao roteiro
juridico.

### Passo 4 — HANDOFF (nao produz aqui)
Casos que justificam **notificacao extrajudicial ou cobranca judicial**
sao **sinalizados**, nunca redigidos por esta skill. Emitir o bloco fixo
de `config/compliance.json` (`handoff_extrajudicial`):

> Casos de inadimplencia que justificam notificacao extrajudicial ou
> cobranca judicial sao handoff para o modulo juridico do ecossistema —
> este plugin sinaliza, nao produz a peca.

Apontar o(s) devedor(es) candidato(s) e o **proximo passo opcional** (§9),
sem afirmar que a acao e cabivel — isso e juizo do advogado.

## 6. OUTPUT — MODELO

```markdown
# Contas a Receber — [recorte] — aging em [DD/MM/AAAA]
**Recorte:** [...]

## Aging
| Faixa | Valor | Qtd | % do AR |
|-------|-------|-----|---------|
| A vencer | R$ [x] | [n] | [%] |
| 1-30 | ... |
| 31-60 | ... |
| 61-90 | ... |
| +90 | R$ [w] | [n] | [%] |
Total a receber: R$ [total]   |   Em atraso: R$ [atraso] ([%])

## Ranking de inadimplentes (valor x dias)
1. [devedor] — R$ [v] — [dias]d atraso — faixa [+90] — score [s]
2. ...

## Fila de cobranca
- Lembrete (1-30d): [devedores]
- Cobranca ativa (31-60d): [devedores]
- Cobranca formal (61-90d): [devedores]
- **HANDOFF juridico (+90d / valor alto):** [devedores]
  > [texto handoff_extrajudicial de config/compliance.json]

## Comentario de CFO
[3-5 linhas: concentracao do risco, impacto no caixa, provisao p/
devedores duvidosos se +90 relevante]
```

## 7. COMENTARIO DE CFO — COMO LER CADA NUMERO

- **AR concentrado em +90:** dinheiro que provavelmente nao volta inteiro
  — avaliar **provisao para devedores duvidosos** e parar de tratar como
  caixa futuro certo no fluxo.
- **Poucos devedores, muito valor:** risco concentrado — perder um cliente
  desses derruba o mes. Priorizar relacionamento + cobranca firme.
- **Muito 1-30:** geralmente processo de cobranca frouxo, nao
  inadimplencia real — um lembrete sistematico recupera a maior parte.

## 8. PROIBICOES

1. NUNCA redigir notificacao extrajudicial ou peca de cobranca — handoff.
2. NUNCA afirmar "cabe acao", "esta em mora", "inadimplencia configurada"
   — qualificacao juridica e do advogado.
3. NUNCA disparar cobranca a devedor (sem conector externo aqui).
4. NUNCA estimar valor/vencimento ausente — sinaliza pendencia.
5. NUNCA contar recebivel intragrupo como AR real do consolidado.
6. NUNCA imprimir devedor/valor/contato em texto plano em log.

## 9. INTEGRACAO

- **Acionada por:** `cfo-master`, `/cfo-receber`.
- **Aciona em apoio:** `fluxo-de-caixa` (AR alimenta a projecao),
  `provisoes` (devedores duvidosos), `consolidacao-multi-entidade`.
- **Encadeia:** `auditoria-cfo` (R1-R4 obrigatoria antes da entrega).

### 💡 Proximos passos opcionais (handoff — sugestao, nao execucao)

| Proximo passo | Comando | Plugin necessario |
|---------------|---------|-------------------|
| Notificacao extrajudicial de cobranca | `/execucao notificacao-mora` | `execucao-adv-os` |
| Acao de cobranca / monitoria | `/execucao cobranca` | `execucao-adv-os` |
| Calculo de debito com correcao + juros | `/calculos calculo-debito` | `calculosjudiciais-adv-os` |

> Se o plugin nao estiver instalado, exportar o ranking acima e tratar o
> caso manualmente com assessoria juridica.
