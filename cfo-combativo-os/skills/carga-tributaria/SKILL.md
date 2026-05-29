---
name: carga-tributaria
description: >
  CARGA-TRIBUTARIA — Consolida (INFORMATIVO, nao consultivo) os
  tributos destacados nas NF-e/NFS-e ingeridas (ICMS, ISS, PIS,
  COFINS, IPI) por competencia e calcula a CARGA EFETIVA sobre o
  faturamento da entidade. Organiza num eixo temporal: Presente
  (ISS/ICMS/PIS/COFINS VIGENTES em 2026, com extincao GRADUAL
  2027-2032 — nunca tratados como ja extintos), Prospectivo
  (impacto da Reforma EC 132/2023 + LC 214/2025 — IBS/CBS/IS, sem
  confundir os dois instrumentos) e Transicao (cronograma).
  NAO faz planejamento tributario: planejamento formal (regime,
  reorganizacao, parecer) e handoff ao tributario-societario-adv-os.
  Use quando o operador pedir carga tributaria, quanto pago de
  imposto, peso dos tributos sobre faturamento, ICMS/ISS/PIS/COFINS
  destacado, ou impacto da reforma tributaria nas contas da empresa.
---

# CARGA-TRIBUTARIA — Tributos Destacados e Carga Efetiva

> Camada F · informativo. CFO senior, direto. Sem afirmar ilegalidade.
> Quatro travas ativas (design-spec §1). DESPERSONALIZADO.

## 1. ESCOPO

Skill **informativa**: lê os tributos que JÁ ESTÃO DESTACADOS nas notas
fiscais ingeridas e consolida a carga real da entidade. **Não** sugere
elisão, não escolhe regime, não emite parecer. Quando o operador pedir
planejamento → **handoff** (§6).

Cobre: **ICMS** (estadual), **ISS** (municipal), **PIS** e **COFINS**
(federais), **IPI** (federal). Lê do schema canônico (design-spec §3)
e dos itens de nota produzidos por `ingest-notas-fiscais`.

## 2. INPUT

- Entidade(s) + período (competência YYYY-MM ou intervalo) + recorte.
- NF-e/NFS-e já ingeridas (tributos destacados por item: base, alíquota,
  valor). Se não houver notas no período → declarar a ausência, não
  estimar (trava 4).
- Faturamento da competência (das notas de saída / receita conciliada).

## 3. PROCESSAMENTO — EIXO TEMPORAL (regra dura)

### 3.1 PRESENTE — tributos VIGENTES em 2026
ISS, ICMS, PIS, COFINS e IPI **estão em vigor em 2026** e continuam
sendo cobrados. A Reforma os extingue de forma **GRADUAL entre 2027 e
2032** — **NUNCA** tratá-los como já extintos. Em 2026 a carga é 100%
sistema atual.

Consolidar por competência:
```
Por tributo: Σ valor destacado nas notas do período
Carga efetiva (%) = Σ tributos destacados / faturamento do período × 100
```
Exibir tabela por tributo + total + carga efetiva %. Separar tributo
sobre saída (débito) de crédito de entrada quando a nota informar
(ICMS/IPI não-cumulativos; PIS/COFINS no regime não-cumulativo).
Se a nota não traz crédito de entrada → reportar só o destacado e
**avisar que é carga bruta, não líquida** (não inventar crédito).

### 3.2 PROSPECTIVO — Reforma EC 132/2023 + LC 214/2025
A Reforma cria DOIS instrumentos novos. **Nunca confundir:**

| Novo tributo | Substitui | Esfera | Sigla |
|---|---|---|---|
| **CBS** — Contrib. sobre Bens e Serviços | PIS + COFINS | Federal | CBS |
| **IBS** — Imposto sobre Bens e Serviços | ICMS + ISS | Estadual+Municipal | IBS |
| **IS** — Imposto Seletivo | (sobretaxa de bens nocivos) | Federal | IS |

- **CBS** ≠ **IBS**. CBS é a fusão federal (PIS+COFINS); IBS é a fusão
  estadual+municipal (ICMS+ISS). IPI será praticamente zerado (mantido
  só por causa da Zona Franca de Manaus).
- Modelo: IVA dual, não-cumulativo, cobrança no destino, crédito amplo.
- A LC 214/2025 regulamenta. Alíquota de referência ainda em definição
  por ato infralegal/Senado → **não chumbar percentual** (trava 4). Se
  o operador pedir simulação com alíquota, declarar que o número ainda
  não é definitivo e pedir a premissa, ou remeter ao handoff.

### 3.3 TRANSIÇÃO — cronograma (informativo)
```
2026  Sistema atual integral (ISS/ICMS/PIS/COFINS/IPI vigentes).
2026  CBS em teste (alíquota simbólica, sem recolhimento efetivo).
2027  CBS entra em vigor; PIS/COFINS extintos; IS começa.
2029  IBS começa gradual; ICMS/ISS começam a reduzir.
2029-2032  Transição progressiva (proporções anuais ICMS/ISS↓ IBS↑).
2033  Sistema novo pleno; ICMS/ISS/IPI extintos.
```
Apresentar como linha do tempo. Marcar onde a entidade está hoje (2026
= sistema atual integral). **Datas/proporções da transição podem ser
ajustadas por norma — avisar para conferir o texto vigente.**

## 4. OUTPUT

```markdown
## Carga tributária — [entidade/recorte] · [competência]

### Presente (2026 — sistema vigente)
| Tributo | Esfera | Valor destacado | % do faturamento |
|---|---|---|---|
| ICMS | Estadual | R$ ___ | __% |
| ISS | Municipal | R$ ___ | __% |
| PIS | Federal | R$ ___ | __% |
| COFINS | Federal | R$ ___ | __% |
| IPI | Federal | R$ ___ | __% |
| **Total** | | **R$ ___** | **__% (carga efetiva)** |

> Carga BRUTA destacada nas notas. Crédito de entrada [considerado/não
> disponível nas notas].

### Prospectivo (Reforma — EC 132/2023 + LC 214/2025)
- PIS+COFINS → **CBS** (federal).  ICMS+ISS → **IBS** (estadual+mun.).
- + **IS** (seletivo) sobre bens específicos.  IPI praticamente zerado.
- Alíquota de referência ainda não definida em norma → sem simulação
  numérica definitiva.

### Transição (cronograma)
[linha do tempo 2026 → 2033, marcando onde a entidade está]
```

## 5. AUDITORIA-CFO
Antes de entregar: R1 (notas do período lidas? faturamento com origem?),
R2 (somatórios conferidos; nenhum percentual de reforma fabricado),
R3 (sem afirmação de ilegalidade/elisão; handoff presente; LGPD),
R4 (eixo temporal completo: presente+prospectivo+transição; recorte ok).

## 6. HANDOFF (compartimentação — trava de escopo)

```
> Esta consolidação é INFORMATIVA. Planejamento tributário formal
> (escolha/troca de regime, reorganização societária, parecer,
> aproveitamento de créditos, estratégia de transição) é escopo de
> assessoria especializada — fora deste plugin.
```
Cross-link (sugestão, não executa):

| Próximo passo | Comando | Plugin |
|---|---|---|
| Planejamento tributário / regime | /tributario diagnostico-regime | tributario-societario-adv-os |
| Apuração e obrigações fiscais | /contabil apuracao-tributos | auditoria-contabil-os |

## 7. PROIBIÇÕES
1. **NUNCA** tratar ISS/ICMS/PIS/COFINS como extintos em 2026 (estão
   vigentes; extinção é gradual 2027-2032).
2. **NUNCA** confundir CBS (federal = PIS+COFINS) com IBS (estadual+mun.
   = ICMS+ISS).
3. **NUNCA** chumbar alíquota da reforma (ainda não definitiva — trava 4).
4. **NUNCA** sugerir elisão, troca de regime ou "como pagar menos" — isso
   é planejamento = handoff.
5. **NUNCA** estimar tributo quando não há nota no período — declarar.
6. **NUNCA** afirmar que um tributo é indevido/ilegal.
