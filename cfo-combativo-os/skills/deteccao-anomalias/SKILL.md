---
name: deteccao-anomalias
description: >
  DETECCAO-ANOMALIAS — O CFO que fareja o fora do padrao. Varre as
  transacoes (schema canonico) e sinaliza: valores fora do padrao
  historico da categoria/contraparte, frequencia anormal, contraparte
  NOVA com valor relevante, PAGAMENTOS DUPLICADOS (mesmo valor+data+
  contraparte), debitos recorrentes esquecidos (assinaturas zumbis),
  tarifas bancarias acima do contratado e — critico para holding —
  DESPESA PESSOAL pagando pela PJ e despesa da PJ pela PF (confusao
  patrimonial, premortem C7). Aponta o achado e o impacto; nunca acusa
  de fraude nem afirma ilegalidade. Use quando o operador pedir achar
  gastos estranhos, transacoes suspeitas, paguei duas vezes,
  assinaturas que esqueci, tarifas altas, confusao PF/PJ, vazamento de
  caixa, ou auditar movimentacoes fora do padrao.
---

# DETECCAO-ANOMALIAS — Fora do Padrão

> Camada F · CFO senior. Quatro travas ativas. DESPERSONALIZADO.
> Sinaliza para revisão humana. **Nunca** rotula como fraude/crime.

## 1. ESCOPO

Detecção por **regra + estatística simples** sobre o histórico da própria
entidade (não modelo externo). Cada achado vem com o **porquê** e o
**impacto em R$**, para o operador decidir. Funciona PJ e PF.

## 2. INPUT
- Entidade(s) + janela de análise + recorte.
- Transações do consolidado SQLite (histórico para baseline). Pouco
  histórico (<2-3 meses) → reduzir sensibilidade e avisar que a baseline
  é curta (trava 4 — não fabricar confiança que não há).

## 3. DETECTORES

### 3.1 Valor fora do padrão
Por categoria/contraparte, baseline = mediana + desvio do histórico.
```
flag SE |valor| > mediana_categoria + k × desvio   (k default 3)
```
Mostrar o valor, a baseline e quanto excedeu. Não usar média pura
(sensível a outlier) — usar mediana.

### 3.2 Frequência anormal
Contraparte recorrente (mensal) que aparece **2×** no mesmo período, ou
sumiu (era recorrente e não veio) → sinalizar (pode ser duplicidade,
adiantamento ou serviço cortado).

### 3.3 Contraparte nova relevante
Primeira ocorrência de uma contraparte com valor acima de um piso
(p.ex. > 1% do volume do período) → sinalizar para conferência (não é
erro, é "olhe isto").

### 3.4 Pagamento duplicado
```
flag SE existem 2+ transações com mesmo (contraparte, valor, sinal=D)
        dentro de janela curta (default 5 dias)
```
Forte candidato a duplicidade — quantificar o valor potencialmente
recuperável. Distinguir de parcela legítima (avisar a hipótese, não
afirmar).

### 3.5 Assinaturas zumbis
Débito recorrente de mesmo valor/contraparte por N meses, tipicamente de
serviço (SaaS, app, mensalidade) → listar com gasto anualizado
(valor × 12) para o operador decidir manter/cancelar.

### 3.6 Tarifas bancárias acima do contratado
Tarifas (categoria `financeiro`) comparadas ao pacote contratado **se o
operador informou** o pacote. Sem o contratado → listar tarifas e seu
total, sem afirmar que estão "acima" (trava 4).

### 3.7 ⭐ Confusão patrimonial PF↔PJ (premortem C7 — risco holding)
Cruza categoria × tipo da entidade dona da conta:
- Despesa de natureza **pessoal** (mercado, lazer, saúde pessoal,
  escola) paga por conta de entidade **PJ**.
- Despesa de natureza **empresarial** (fornecedor, folha, insumo) paga
  por conta **PF**.

```
flag SE categoria_pessoal E entidade.tipo == 'pj'
flag SE categoria_empresarial E entidade.tipo == 'pf'
```
Reportar como **risco de confusão patrimonial** (relevante para holding /
desconsideração da personalidade jurídica), quantificar o montante, e
fazer **handoff** (§6) — não dar parecer jurídico nem afirmar
ilegalidade (trava 1).

## 4. OUTPUT

```markdown
## Anomalias detectadas — [entidade/recorte] · [janela]

| # | Tipo | Transação | Por que chamou atenção | Impacto R$ |
|---|---|---|---|---|
| 1 | Duplicidade | [data/contraparte] | 2 débitos iguais em 3 dias | R$ ___ |
| 2 | Assinatura zumbi | [contraparte] | recorrente 8m; R$ X/mês | R$ ___/ano |
| 3 | Confusão PF↔PJ | [data/contraparte] | despesa pessoal na PJ | R$ ___ |
| ... | | | | |

**Total potencialmente recuperável/revisável:** R$ ___
[comentário de CFO: o que conferir primeiro; baseline curta? avisar]
```
Sem achados → dizer claramente "nada fora do padrão nesta janela"
(não inventar achado).

## 5. AUDITORIA-CFO
R1 (histórico suficiente para baseline? período lido?), R2 (regras/limiar
conferidos; nada fabricado; baseline curta declarada), R3 (nenhum achado
rotulado como fraude/crime; confusão patrimonial com handoff; LGPD/
mascaramento de contraparte), R4 (todos os 7 detectores rodados; recorte ok).

## 6. INTEGRAÇÃO / HANDOFF
Consome consolidado SQLite. Alimenta `relatorio-executivo`.

```
> Confusão patrimonial é um achado financeiro, não um parecer. A
> análise de desconsideração da personalidade jurídica / blindagem
> patrimonial é escopo de assessoria especializada.
```
| Próximo passo | Comando | Plugin |
|---|---|---|
| Estruturação de holding / patrimônio | /tributario reorganizacao-societaria | tributario-societario-adv-os |

## 7. PROIBIÇÕES
1. **NUNCA** rotular achado como fraude, crime, lavagem ou desvio
   doloso — é "fora do padrão, conferir".
2. **NUNCA** afirmar ilegalidade na confusão patrimonial — sinalizar +
   handoff (trava 1).
3. **NUNCA** afirmar tarifa "acima do contratado" sem o pacote informado.
4. **NUNCA** inventar achado quando não há — declarar "nada fora do padrão".
5. **NUNCA** confiar em baseline curta sem avisar.
