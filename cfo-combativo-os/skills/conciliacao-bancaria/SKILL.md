---
name: conciliacao-bancaria
description: >
  CONCILIACAO-BANCARIA — Coracao da triagem. Casa transacao bancaria x
  nota fiscal x lancamento por valor + data (janela) + contraparte (fuzzy),
  lendo a base local da entidade. Sinaliza pendencias (lancamento sem nota,
  nota sem pagamento, divergencia de valor, duplicidade) e separa
  conciliado x pendente para a contabilidade. MARCA
  is_transferencia_intragrupo quando a contraparte e outra entidade do
  mesmo grupo do grafo (premortem C7 — evita contar receita/despesa 2x no
  consolidado). Orquestra o engine canonical (scripts/lib/canonical.py).
  Use quando o operador disser "conciliar", "conciliacao bancaria", "casar
  extrato com notas", "o que esta pendente", "bater extrato e lancamentos",
  "/cfo-conciliar".
---

# CONCILIACAO-BANCARIA — O Coracao da Triagem

## 1. ESCOPO

Cruza as tres fontes ja ingeridas (transacoes do extrato, notas fiscais,
lancamentos) na base da entidade e produz o estado de conciliacao:
o que casou, o que esta pendente e por que. E o que torna a triagem
contabil confiavel.

Tambem **marca transferencias intragrupo** — vital para o consolidado
multi-entidade nao inflar (premortem C7).

NAO produz peca de cobranca (handoff ao ecossistema), NAO afirma
ilegalidade, NAO inventa lancamento (trava 4).

## 2. INPUT NECESSARIO

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `entidade_id` | sim | Entidade a conciliar — **PERGUNTAR** se ausente |
| `competencia` | sim | Mes (YYYY-MM) ou intervalo |
| `janela_dias` | opcional | Tolerancia de data data nota vs pagamento (default 5d) |
| `tolerancia_valor` | opcional | Diferenca aceita por arredondamento (default R$ 0,01) |

Pre-requisito: extrato e notas da competencia ja ingeridos (camada A).

## 3. PROCESSAMENTO

### Passo 1 — Carregar a base da entidade

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lib/canonical.py --conciliar \
  --entidade <entidade_id> --competencia <YYYY-MM> \
  --janela <dias> --tolerancia <valor>
```

O engine carrega transacoes + notas + lancamentos do `base.sqlite` e
roda o matching. Degradacao graciosa: se faltar `rapidfuzz` para o fuzzy
de contraparte, cai num matcher por normalizacao de string (stdlib) —
nunca crasha (premortem C2).

### Passo 2 — Regras de matching

Casa **transacao × nota × lancamento** quando:
1. **Valor** dentro de `tolerancia_valor` (default R$ 0,01).
2. **Data** dentro de `janela_dias` (data da nota vs data do pagamento).
3. **Contraparte** com match fuzzy (nome/doc normalizado; threshold
   conservador — abaixo do limiar vira "candidato a confirmar", nao
   match automatico).

Match com os 3 criterios fortes → `conciliado`. Match parcial →
`candidato` (exibe para o operador confirmar). Sem match → `pendente`.

### Passo 3 — Sinalizar pendencias

| Tipo de pendencia | Significado |
|---|---|
| Lancamento sem nota | Saiu/entrou dinheiro sem nota vinculada |
| Nota sem pagamento | Nota emitida/recebida sem transacao correspondente |
| Divergencia de valor | Casou contraparte+data mas valor difere alem da tolerancia |
| Duplicidade | Dois lancamentos/notas iguais — possivel pagamento duplo |

Cada pendencia recebe o `id` da transacao/nota e o motivo. Nada e
descartado — tudo vai para o relatorio de pendencias da triagem.

### Passo 4 — MARCAR transferencia intragrupo (premortem C7)

Para cada transacao **sem nota** mas com contraparte que **casa com outra
entidade do MESMO grupo** no `cfo-state.json`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lib/canonical.py --marcar-intragrupo \
  --entidade <entidade_id> --competencia <YYYY-MM>
```

- Seta `is_transferencia_intragrupo = true` na transacao + categoria
  `transferencia-intragrupo` (config/categorias.json).
- Idealmente casa **os dois lados** (debito na entidade A = credito na
  entidade B do mesmo grupo) e marca o par.
- Esse flag e **eliminado** nos recortes grupo/total da
  `consolidacao-multi-entidade` — evita contar R$ 2x (ex.: R$ 50k da
  alfa para a PF do socio nao vira receita PF + despesa PJ no consolidado).
- Fronteira PF↔PJ permanece **explicita** no relatorio.

### Passo 5 — Persistir o resultado

Grava o estado de conciliacao (conciliado/candidato/pendente +
`doc_vinculado` quando casou) de volta no `base.sqlite`, append-only por
competencia. Backup antes de salvar.

## 4. OUTPUT

```markdown
## 🔗 Conciliacao — {{entidade}} · {{competencia}}

| Estado | Qtd | Valor |
|---|---:|---:|
| Conciliado | 118 | R$ ... |
| Candidato (confirmar) | 7 | R$ ... |
| Pendente | 22 | R$ ... |
| Transferencia intragrupo (marcada) | 4 | R$ ... |

### ⚠️ Pendencias
| # | Tipo | Contraparte | Valor | Motivo |
|---|---|---|---:|---|
| 1 | Lancamento sem nota | [...] | R$ ... | Saida sem NF vinculada |
| 2 | Nota sem pagamento | [...] | R$ ... | NF-e emitida, sem credito |
| 3 | Divergencia de valor | [...] | R$ ... | Nota R$ 1.000 / pago R$ 980 |
| 4 | ⚠️ Duplicidade | [...] | R$ ... | Possivel pagamento duplo |

### Candidatos a confirmar (match parcial)
[lista — operador confirma ou rejeita cada um]

### 🔁 Transferencias intragrupo marcadas
- [alfa → PF socio: R$ 50.000 em 12/04 — eliminada no consolidado do grupo]

> Confusao patrimonial (despesa pessoal na PJ / vice-versa) e sinalizada
> separadamente por `deteccao-anomalias`.
```

## 5. PROIBICOES

1. **Nunca** casar automaticamente com match fraco — vira `candidato`.
2. **Nunca** descartar pendencia silenciosamente — tudo vai ao relatorio.
3. **Nunca** deixar de marcar transferencia intragrupo detectada (C7).
4. **Nunca** inventar lancamento para "fechar" a conciliacao (trava 4).
5. **Nunca** produzir peca de cobranca aqui (handoff ao ecossistema).
6. **Nunca** propagar excecao de import ao Cowork (premortem C2).

## 6. INTEGRACAO

- **Upstream:** camada A (`ingest-extrato-bancario`, `ingest-notas-fiscais`).
- **Downstream:** `triagem-contabil`, `consolidacao-multi-entidade`
  (usa o flag intragrupo), `deteccao-anomalias`, `fluxo-de-caixa`.
- **Auditoria:** `auditoria-cfo` R1 (conciliacao fechou?).
- **Handoff:** inadimplencia que justifica notificacao →
  `execucao-adv-os` / extrajudicial (sinaliza, nao produz).
