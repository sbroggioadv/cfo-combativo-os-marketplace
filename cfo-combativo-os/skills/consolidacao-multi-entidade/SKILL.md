---
name: consolidacao-multi-entidade
description: >
  CONSOLIDACAO-MULTI-ENTIDADE — Coracao da arquitetura multi-entidade.
  Le o grafo de entidades/grupos/contas do cfo-state.json e entrega os
  TRES recortes de leitura: (1) por entidade — visao individual isolada;
  (2) por grupo — soma das entidades do grupo ELIMINANDO transferencias
  intragrupo (nunca conta 2x — premortem C7); (3) total consolidado —
  visao do operador inteiro com a fronteira PF↔PJ sempre EXPLICITA
  (relevante para holding/planejamento patrimonial). Base para qualquer
  analise que ultrapasse uma entidade. Use quando o operador disser
  "consolidar", "visao do grupo", "tudo junto", "PF + PJ", "minhas
  empresas somadas", "quadro geral", "consolidado", "patrimonio total"
  ou rodar /cfo-consolidar.
---

# CONSOLIDACAO-MULTI-ENTIDADE — Os Tres Recortes

> **Decisao fundadora (design-spec §2):** o operador pode ser PF, PJ ou
> ambos, com multiplas entidades e N contas cada. Esta skill traduz esse
> grafo em visao financeira sem distorcer numeros.

## 1. ESCOPO

CFO de holding/grupo: pega o grafo do `cfo-state.json` e produz os tres
recortes de §2.3, sempre consistentes entre si. O recorte certo depende
da pergunta do gestor — esta skill entrega os tres e destaca o pedido.

## 2. O GRAFO (lido de `cfo-state.json`)

```
GRUPO (opcional)        ENTIDADE (pf|pj)        CONTA (cc|cartao|invest)
grupo-empresas    ──┬── empresa-alfa (pj)  ──┬─ itau-cc-001
                    ├── empresa-beta  (pj)    └─ bb-cc-002
                    └── empresa-gama  (pj)
grupo-familia     ──┬── joao   (pf)        ──┬─ nubank-001
                    └── maria  (pf)           └─ c6-cc-002
```
- Entidade: unidade patrimonial (PF=CPF mascarado, PJ=CNPJ mascarado),
  tipo, regime tributario (PJ), grupo_id (0 ou 1), inicio.
- Toda transacao pertence a 1 conta → 1 entidade. Grupos sao opcionais.

**Le o estado** via `scripts/resolve-state.py` / `scripts/state.py`:
```
python3 scripts/resolve-state.py            # resolve o state ativo
```
Histórico consolidado por entidade vive em
`<cwd>/.cfo/entidades/{id}/base.sqlite` (append-only por competencia,
§2.4) — nunca rebuild destrutivo (premortem C8).

## 3. OS TRES RECORTES (§2.3)

### 3.1 Por entidade
Visao individual isolada (empresa-alfa sozinha; joao sozinho). Toda
transacao da entidade conta normalmente. **Transferencias intragrupo
permanecem visiveis** aqui (sao reais para a entidade individual).

### 3.2 Por grupo (ELIMINA intragrupo)
Soma das entidades do grupo, **eliminando transferencias intragrupo**
(premortem C7):
- Identificar transacoes com `is_transferencia_intragrupo = true`
  (marcadas por `conciliacao-bancaria` quando contraparte = outra
  entidade do mesmo grupo).
- **Excluir do agregado** — nao contar 2x (a saida de alfa + a entrada
  de beta sao a mesma R$, nao R$ dobrada).
- Exemplo da armadilha: alfa transfere R$50k para beta. Sem eliminacao,
  o grupo "fatura" R$50k a mais e "gasta" R$50k a mais → KPIs inflados.
  Com eliminacao → R$0 de efeito no consolidado do grupo (so movimentou
  caixa interno).

### 3.3 Total consolidado (grupo de tudo)
Visao do operador inteiro. Soma todas as entidades, eliminando
transferencias intra-grupo de TODOS os grupos. **Fronteira PF↔PJ sempre
explicita:**
- Transferencia PJ→PF (pro-labore, distribuicao de lucro, mutuo) NAO e
  "intragrupo eliminavel" automaticamente — e movimentacao entre esferas
  patrimoniais distintas com tratamento tributario proprio.
- O consolidado total mostra **subtotal PJ + subtotal PF + total**,
  nunca funde os dois num numero unico sem rotulo (relevante para
  holding/planejamento patrimonial).
- Despesa pessoal paga pela PJ (ou vice-versa) → sinalizar confusao
  patrimonial (handoff a `deteccao-anomalias`).

## 4. OUTPUT

```markdown
## 🏛️ Consolidacao Multi-Entidade · {{competencia}}

**Grafo:** {{n_entidades}} entidades · {{n_grupos}} grupos · {{n_contas}} contas
**Recorte pedido:** {{entidade X | grupo Y | total}}

### Recorte 1 — Por Entidade
| Entidade | Tipo | Receita | Despesa | Resultado | Caixa |
|---|:--:|---:|---:|---:|---:|
| empresa-alfa | PJ | R$ ... | R$ ... | R$ ... | R$ ... |
| joao | PF | R$ ... | R$ ... | R$ ... | R$ ... |

### Recorte 2 — Por Grupo (intragrupo eliminado)
| Grupo | Receita | Despesa | Resultado | Intragrupo eliminado |
|---|---:|---:|---:|---:|
| grupo-empresas | R$ ... | R$ ... | R$ ... | −R$ {{intragrupo}} |

### Recorte 3 — Total Consolidado
| Esfera | Receita | Despesa | Resultado | Caixa |
|---|---:|---:|---:|---:|
| Subtotal PJ | R$ ... | R$ ... | R$ ... | R$ ... |
| Subtotal PF | R$ ... | R$ ... | R$ ... | R$ ... |
| **TOTAL** | **R$ ...** | **R$ ...** | **R$ ...** | **R$ ...** |

> Fronteira PF↔PJ explicita. Transferencias PJ↔PF: R$ {{cruzou_esfera}}
> (movimentacao entre esferas — nao eliminada, sinalizada).

### ⚠️ Sinais
- [confusao patrimonial detectada? → handoff deteccao-anomalias]
- [entidade nova no mes X nao invalida meses anteriores — historico monotonico]
```

## 5. PERSISTENCIA INCREMENTAL (trava §2.4)

- Setup define o grafo; alteravel a qualquer tempo (adicionar entidade /
  conta / grupo) **sem perder o consolidado ja construido** — so agrega.
- Adicionar entidade no mes 7 **nao invalida** os meses 1-6 das outras.
- Reprocessar um mes substitui SO aquele mes daquela conta
  (idempotencia por `(entidade, conta, competencia)`) — nunca rebuild
  destrutivo. `state.py` faz backup antes de salvar.

## 6. INTEGRACAO

### Upstream
- `cfo-master` (roteia /cfo-consolidar ou pergunta de grupo/total)
- `conciliacao-bancaria` (marca `is_transferencia_intragrupo`)
- `cfo-onboarding` (define o grafo)

### Downstream
- `auditoria-cfo` — R4 confere recortes corretos; R1 confere que
  intragrupo foi eliminado e que nenhuma entidade sumiu.
- `dashboard-html` — alimenta o **seletor de recorte** (entidade/grupo/total).
- `relatorio-executivo` — narra o consolidado.

## 7. PROIBICOES

1. **Nunca** somar transferencia intragrupo no recorte grupo/total
   (premortem C7) — sempre eliminar as marcadas.
2. **Nunca** fundir PF e PJ num numero unico sem rotular a esfera.
3. **Nunca** tratar transferencia PJ↔PF como intragrupo eliminavel —
   e cruzamento de esfera, sinalizado.
4. **Nunca** fazer rebuild destrutivo do historico ao reprocessar um mes.
5. **Nunca** deixar de mostrar a entidade individual quando o operador
   pedir o consolidado (sempre os tres recortes disponiveis).

## 💡 Proximos passos opcionais

| Proximo passo | Comando |
|---|---|
| Editar o grafo de entidades | `/cfo-setup` |
| Conciliar para marcar intragrupo | `/cfo-conciliar` |
| Ver no dashboard com seletor de recorte | `/cfo-dashboard` |
| Planejamento patrimonial (holding) | assessoria especializada (fora do plugin) |

> Consolidacao financeira. Estruturacao societaria/holding e escopo de
> assessoria especializada — handoff, nao se mistura aqui.
