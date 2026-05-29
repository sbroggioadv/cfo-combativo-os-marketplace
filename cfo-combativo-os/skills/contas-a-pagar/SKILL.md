---
name: contas-a-pagar
description: >
  CONTAS-A-PAGAR — Gestao de AP. Agenda de vencimentos, urgencia
  (vencidas / hoje / proximos 7d / proximos 30d) PONDERADA POR VALOR,
  fornecedores recorrentes, e ORDEM OTIMA DE PAGAMENTO quando o caixa e
  insuficiente (custo de atraso x criticidade x relacao). Suporta os tres
  recortes multi-entidade (entidade / grupo / total). Use quando o
  operador disser "contas a pagar", "o que vence essa semana", "nao tenho
  caixa pra tudo, o que pago primeiro?", "minha agenda de pagamentos",
  "fornecedores", "/cfo-pagar". Le o consolidado via
  scripts/lib/canonical.py, nunca fabrica numero (trava 4).
---

# CONTAS-A-PAGAR — Agenda, Urgencia e Ordem Otima

## 1. ESCOPO

Skill Camada B (Analise) do `cfo-combativo-os`. Organiza o **passivo
circulante operacional** — o que a entidade deve e quando. Tres entregas:
(1) **agenda de vencimentos**, (2) **urgencia ponderada por valor**, e (3)
a decisao mais cara de gestor: **em que ordem pagar quando o caixa nao
cobre tudo**.

**Acionada por:** "contas a pagar", "o que vence essa semana", "nao tenho
caixa pra tudo", "agenda de pagamentos", `/cfo-pagar`.

**NAO faz:** executar pagamento (o plugin nunca movimenta dinheiro),
ingestao, envio externo.

## 2. AS QUATRO TRAVAS (sempre)

1. **Municao, nunca veredito** — sugere ordem de pagamento; a decisao e
   do operador. Nao afirma inadimplencia/mora em termos juridicos.
2. **Gate de envio humano** — esta skill nao dispara nada (nem boleto,
   nem aviso). So organiza.
3. **Dado sensivel local** — fornecedores, valores e contas ficam na
   maquina; mascarar em log.
4. **Nunca fabricar** — vencimentos e valores vem do consolidado. AP sem
   data ou sem valor → sinaliza como pendencia, nao inventa.

## 3. FONTE DE DADOS — ORQUESTRA, NAO REIMPLEMENTA

- `scripts/lib/canonical.py` — le o consolidado SQLite, aplica o recorte
  e elimina transferencias intragrupo (uma "transferencia" para outra
  entidade do mesmo grupo **nao e** conta a pagar real do consolidado).
- `scripts/lib/kpi_engine.py` — buckets de aging de pagamento, score de
  urgencia ponderado e o solver de ordem otima sob restricao de caixa.

A skill **nao calcula a ponderacao no markdown** — pede ao engine e
escreve o comentario sobre o resultado.

## 4. INPUT NECESSARIO

- **Recorte:** entidade / grupo / total.
- **Horizonte:** semana, mes, ou ate data X.
- **Caixa disponivel** para o exercicio de ordem otima — vem do
  `fluxo-de-caixa` (caixa livre apos provisoes). Sem ele, a skill faz a
  agenda + urgencia mas **declara** que nao pode otimizar ordem sem saber
  o caixa.
- **Criticidade dos fornecedores** (opcional, melhora a ordem): quais sao
  essenciais a operacao (corte = para a empresa) vs adiaveis.

## 5. PROCESSAMENTO

### Passo 1 — Agenda de vencimentos
Listar AP do horizonte por data, com fornecedor (mascarado em log),
valor, e categoria. Marcar recorrentes (assinaturas, folha, aluguel,
tributos a vencer) — recorrencia muda a leitura de risco.

### Passo 2 — Urgencia ponderada por valor
Distribuir em buckets e ponderar pelo montante de cada um:

| Bucket | Peso de urgencia |
|--------|------------------|
| **Vencidas** | maximo — ja em atraso, custo de mora correndo |
| **Vencem hoje** | alto |
| **Proximos 7 dias** | medio-alto |
| **Proximos 30 dias** | medio — planejavel |

Urgencia nao e so "quantas contas" — e **quanto R$ esta em cada bucket**.
Dez contas pequenas vencidas pesam menos que uma grande hoje. O engine
retorna o score ponderado; a skill ranqueia.

### Passo 3 — Ordem otima sob caixa insuficiente
Quando caixa livre < total a pagar do horizonte, ordenar por:

1. **Custo de atraso** — multa/juros contratual, corte de servico
   essencial, perda de desconto por antecipacao.
2. **Criticidade operacional** — fornecedor sem o qual a operacao para
   (energia, folha, insumo critico) vem antes do adiavel.
3. **Relacao** — fornecedor estrategico que se preserva vs avulso.
4. **Tributos** — tratar a parte: atraso tributario tem regra propria;
   sinalizar, nao improvisar enquadramento.

Saida: **lista priorizada do que pagar com o caixa disponivel** + o que
sobra para a janela seguinte + **quanto falta** para cobrir tudo. Onde
houver multa/juros de mora contratual, usar o valor do contrato; se nao
houver dado, declarar — **nunca estimar a multa** (trava 4).

### Passo 4 — Comentario de CFO
Para cada corte sugerido, explicar o *porque* em uma linha: "adiar este
porque o custo de atraso (R$ X) e menor que a multa do essencial (R$ Y)".

## 6. OUTPUT — MODELO

```markdown
# Contas a Pagar — [recorte] — [horizonte]
**Recorte:** [...]   **Data-base:** [DD/MM/AAAA]
**Caixa livre informado:** R$ [valor] (de fluxo-de-caixa) | [nao informado]

## Agenda de vencimentos
| Vencimento | Fornecedor | Valor | Categoria | Recorrente |
|------------|-----------|-------|-----------|------------|

## Urgencia ponderada
- Vencidas: R$ [x] ([n] contas) — [comentario]
- Hoje: R$ [y] ([n])
- 7 dias: R$ [z] ([n])
- 30 dias: R$ [w] ([n])
Total a pagar no horizonte: R$ [total]

## Ordem otima (caixa insuficiente)
[so quando caixa < total]
1. PAGAR: [fornecedor] R$ [v] — motivo: [custo de atraso / essencial]
2. PAGAR: ...
...
ADIAR para [janela]: [fornecedor] R$ [v] — motivo: [adiavel / custo baixo]
**Caixa cobre ate o item N. Falta R$ [gap] para o restante.**

## Comentario de CFO
[3-5 linhas: onde esta o risco, o que renegociar, o que antecipar receita]
```

## 7. COMENTARIO DE CFO — COMO LER CADA NUMERO

- **Muito R$ vencido:** nao e so o valor — e o custo de mora correndo +
  sinal de gestao de caixa apertada. Atacar primeiro.
- **Concentracao em um dia:** vencimentos empilhados criam ruptura
  artificial; negociar diluicao de datas com fornecedores resolve sem
  injetar caixa.
- **Tributo no meio da fila:** sempre destacar a parte — atraso
  tributario nao se trata como atraso de fornecedor comum.

## 8. PROIBICOES

1. NUNCA executar/agendar pagamento — o plugin nao movimenta dinheiro.
2. NUNCA estimar multa/juros de mora sem o dado contratual.
3. NUNCA priorizar so por valor — ponderar custo de atraso x criticidade.
4. NUNCA afirmar mora/inadimplencia em termos juridicos.
5. NUNCA contar transferencia intragrupo como AP real do consolidado.
6. NUNCA imprimir fornecedor/conta/valor em texto plano em log.

## 9. INTEGRACAO

- **Acionada por:** `cfo-master`, `/cfo-pagar`.
- **Aciona em apoio:** `fluxo-de-caixa` (caixa livre p/ ordem otima),
  `provisoes` (tributos a vencer), `consolidacao-multi-entidade`.
- **Encadeia:** `auditoria-cfo` (R1-R4 obrigatoria antes da entrega).

> Toda saida passa por `auditoria-cfo`. R3 confere que nenhuma afirmacao
> de mora juridica vazou; R4 confere o recorte.
