---
name: provisoes
description: >
  PROVISOES — Mostra o que DEVERIA estar reservado e nao aparece no
  extrato (caixa "falsamente confortavel"). PJ: 13o salario, ferias +
  1/3, rescisoes provaveis, impostos a vencer, honorarios de exito,
  contingencias (trabalhistas/civeis/tributarias). PF: reserva de
  emergencia (em meses de despesa coberta), IRPF anual a pagar,
  previdencia/aposentadoria. Calcula o total que deveria estar
  provisionado por competencia e SINALIZA com alerta quando o caixa
  livre e MENOR que as provisoes devidas (risco silencioso de ruptura).
  Use quando o operador perguntar quanto devo guardar, estou
  provisionando certo, tenho reserva pro 13o/ferias, meu caixa cobre os
  impostos a vencer, qual minha reserva de emergencia, ou pedir o
  colchao/provisao da PF ou da PJ.
---

# PROVISOES — O Que Deveria Estar Reservado

> Camada F · CFO senior. Quatro travas ativas. DESPERSONALIZADO.
> O extrato mostra o que TEM; esta skill mostra o que JÁ É COMPROMISSO
> futuro e ainda não saiu — o caixa parece maior do que é.

## 1. ESCOPO

Distingue **saldo disponível** de **saldo livre real**. Calcula as
obrigações futuras quase-certas (provisões) por entidade e período, e
compara com o caixa livre (de `fluxo-de-caixa`). Funciona para **PJ** e
**PF** — o catálogo de provisões muda conforme o tipo da entidade
(lê `tipo` no `cfo-state.json`).

## 2. INPUT

- Entidade(s) + período + recorte (entidade/grupo/total).
- Histórico de folha / pró-labore (PJ) das competências ingeridas.
- Caixa livre do período (de `fluxo-de-caixa`).
- Contingências e honorários de êxito: o operador informa (não há no
  extrato). Se não informar → listar como **não estimado**, não chutar.

## 3. PROCESSAMENTO

### 3.1 Entidade PJ
Provisões mensais a apurar (acumulam mês a mês):

| Provisão | Base de cálculo |
|---|---|
| 13º salário | folha mensal / 12 (acumula até dezembro) |
| Férias + 1/3 | (folha mensal / 12) × 1,333 |
| Rescisões prováveis | turnover histórico × custo médio de rescisão |
| Impostos a vencer | DAS/DARF/GPS/ICMS/ISS agendados não pagos |
| Honorários de êxito | % contratado × valor provável (informado) |
| Contingências | passivo provável informado (trab./cível/trib.) |

```
Provisão devida no período = Σ das linhas aplicáveis acumuladas
```
13º e férias **acumulam** — provisionar 1/12 ao mês evita o "buraco de
dezembro". Mostrar o saldo acumulado da provisão, não só a parcela do mês.

### 3.2 Entidade PF
| Provisão | Base / parâmetro |
|---|---|
| Reserva de emergência | despesa mensal média × meses-alvo (default 6; autônomo/renda variável → sugerir maior) |
| IRPF anual a pagar | estimativa de imposto a recolher / ajuste anual |
| Previdência / aposentadoria | aporte mensal alvo (informado) |

**Reserva de emergência em MESES cobertos** (não em R$ absoluto):
```
meses cobertos = reserva atual / despesa mensal média
```
Semáforo: <3m vermelho · 3-6m amarelo · ≥6m verde (ajustar alvo
conforme estabilidade de renda informada).

### 3.3 Comparação (o alerta que importa)
```
caixa_livre   = de fluxo-de-caixa (após AP do período)
provisoes_dev = Σ provisões devidas acumuladas

SE caixa_livre < provisoes_dev:
   🔴 ALERTA: caixa não cobre as provisões devidas. Déficit = R$ ___.
   O saldo disponível está mascarando compromissos futuros já assumidos.
SENAO SE caixa_livre < provisoes_dev × 1,2:
   🟡 Cobre, mas com folga apertada (< 20%).
SENAO:
   🟢 Caixa cobre as provisões com folga.
```

## 4. OUTPUT

```markdown
## Provisões — [entidade/recorte] · [competência]

### Provisões devidas (acumuladas)
| Provisão | Valor acumulado |
|---|---|
| ... | R$ ___ |
| **Total devido** | **R$ ___** |
| Não estimado (sem dado) | [lista] |

### Confronto com caixa
| Item | Valor |
|---|---|
| Caixa livre (após AP) | R$ ___ |
| Provisões devidas | R$ ___ |
| **Folga / (déficit)** | **R$ ___** |

[🔴/🟡/🟢 leitura semafórica + comentário de CFO: o que reservar primeiro]
```

PF: incluir card "Reserva de emergência: __ meses cobertos (alvo __)".

## 5. AUDITORIA-CFO
R1 (folha/agendados lidos? período fechado?), R2 (acumulados conferidos;
nada fabricado — contingência/êxito sem dado = "não estimado"),
R3 (sem veredito; LGPD/mascaramento), R4 (PJ e PF tratados conforme tipo;
recorte correto; alerta de déficit visível quando aplicável).

## 6. INTEGRAÇÃO
Consome `fluxo-de-caixa` (caixa livre) e a folha de `ingest-*`. Alimenta
`relatorio-executivo` (entra nas "3-5 coisas do mês") e a resposta de
"quanto posso gastar" do `cfo-master` (gasto livre = caixa − provisões − AP).

## 7. PROIBIÇÕES
1. **NUNCA** apresentar saldo disponível como se fosse livre — sempre
   abater provisões devidas.
2. **NUNCA** estimar contingência ou honorário de êxito sem o operador
   informar — listar como "não estimado".
3. **NUNCA** fixar reserva de emergência em R$ absoluto — expressar em
   meses cobertos.
4. **NUNCA** misturar provisão PJ com PF (catálogo por `tipo` da entidade).
5. **NUNCA** suprimir o alerta de déficit quando caixa < provisões.
