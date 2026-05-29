---
name: orcamento
description: >
  ORCAMENTO — Budget da entidade. Cadastra metas mensais de receita e
  despesa POR CATEGORIA, confronta ORCADO x REALIZADO da competencia,
  calcula desvios (absoluto e %), aponta os ESTOUROS de categoria e
  projeta o FECHAMENTO do mes/ano por run-rate (ritmo realizado ate
  agora extrapolado). Integra com o array metas[] do cfo-state.json
  (le, grava e atualiza metas de orcamento). Recortes por entidade,
  grupo ou total. Use quando o operador pedir orcamento, budget, metas
  do mes, orcado x realizado, estourei o orcamento, em que categoria
  gastei demais, vou fechar o mes/ano dentro da meta, projecao de
  fechamento, ou definir/ajustar metas de gasto por categoria.
---

# ORCAMENTO — Orçado × Realizado e Projeção

> Camada F · CFO senior. Quatro travas ativas. DESPERSONALIZADO.

## 1. ESCOPO

Compara o que foi **planejado** com o que **aconteceu**, por categoria,
e diz se a entidade fecha o período dentro da meta. Funciona para PJ e
PF. As metas de orçamento vivem em `metas[]` do `cfo-state.json` (esta
skill é dona de criar/editar/ler as metas do tipo `orcamento`).

## 2. INPUT

- Entidade(s) + período + recorte.
- Metas de orçamento por categoria (do `cfo-state.json` → `metas[]`). Se
  não houver metas → oferecer cadastrar agora (§3.1).
- Realizado: transações da competência (schema canônico §3), agrupadas
  pela `categoria` auto-classificada.

## 3. PROCESSAMENTO

### 3.1 Cadastro / edição de meta
Grava em `metas[]` do state via `state.py`. Estrutura da meta orçamento:
```json
{"id":"orc-2026-06-marketing","tipo":"orcamento","entidade_id":"empresa-alfa",
 "competencia":"2026-06","categoria":"despesa-marketing","valor_meta":5000.00,
 "sinal":"D","criado_em":"iso"}
```
Append-only por competência (§2.4): editar a meta de um mês não toca os
outros. Receita usa `sinal:C`; despesa `sinal:D`.

### 3.2 Orçado × realizado
Para cada categoria com meta na competência:
```
realizado  = Σ transações da categoria no período (do consolidado)
desvio_abs = realizado − meta
desvio_pct = desvio_abs / meta × 100
```
- Despesa: realizado **acima** da meta = **estouro** (🔴). Abaixo = 🟢.
- Receita: realizado **abaixo** da meta = **furo** (🔴). Acima/igual = 🟢.
- Faixa amarela: dentro de ±10% da meta (configurável).

Categoria com realizado mas **sem meta** → listar como "fora do orçamento"
(gasto não planejado), não silenciar.

### 3.3 Projeção de fechamento (run-rate)
Com o mês ainda em curso (dia D de N):
```
run_rate_categoria = realizado_ate_agora / dias_decorridos × dias_no_periodo
projecao_anual     = realizado_ano_ate_agora / meses_decorridos × 12
```
Comparar projeção × meta → "no ritmo atual, fecha o mês em R$ ___
(__% da meta)". Sinalizar categorias que **projetam estouro** mesmo que
hoje ainda estejam abaixo. Run-rate é projeção linear — declarar a
premissa, não vender como certeza (trava 4).

## 4. OUTPUT

```markdown
## Orçamento — [entidade/recorte] · [competência] (dia D de N)

### Orçado × Realizado
| Categoria | Orçado | Realizado | Desvio | % | Status |
|---|---|---|---|---|---|
| Receita serviços | R$ ___ | R$ ___ | R$ ___ | __% | 🟢/🟡/🔴 |
| Despesa folha | R$ ___ | R$ ___ | R$ ___ | __% | 🟢/🟡/🔴 |
| ... | | | | | |
| **Total** | **R$ ___** | **R$ ___** | **R$ ___** | | |

### Fora do orçamento (gasto sem meta)
| Categoria | Realizado |
|---|---|

### Projeção de fechamento (run-rate · premissa linear)
| Categoria | Projetado fim do período | Meta | Veredito |
|---|---|---|---|
| ... | R$ ___ | R$ ___ | dentro / estoura em R$ ___ |

[comentário de CFO: onde apertar, o que renegociar, o que está saudável]
```

## 5. AUDITORIA-CFO
R1 (transações da competência lidas? metas carregadas do state?),
R2 (desvios e run-rate conferidos; projeção rotulada como premissa
linear), R3 (sem veredito jurídico; LGPD), R4 (todas as categorias com
meta cobertas + bloco "fora do orçamento"; recorte correto).

## 6. INTEGRAÇÃO
Lê/grava `metas[]` (state.py). Consome categorias do consolidado SQLite.
Alimenta `relatorio-executivo` (estouros entram nas prioridades do mês) e
a pergunta "quanto posso gastar" (orçamento restante da categoria).

## 7. PROIBIÇÕES
1. **NUNCA** apresentar run-rate como certeza — é projeção linear,
   declarar a premissa.
2. **NUNCA** silenciar gasto realizado sem meta — listar como "fora do
   orçamento".
3. **NUNCA** sobrescrever metas de outras competências ao editar uma
   (append-only por competência).
4. **NUNCA** inverter a leitura de sinal: estouro de despesa ≠ furo de
   receita.
5. **NUNCA** fabricar meta que o operador não definiu.
