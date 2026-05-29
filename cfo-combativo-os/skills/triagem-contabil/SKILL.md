---
name: triagem-contabil
description: >
  TRIAGEM-CONTABIL — Monta o pacote mensal para a contabilidade de uma
  entidade: seleciona extratos + notas fiscais + conciliacao da
  competencia, gera indice do pacote e relatorio de pendencias (o que
  falta, o que diverge) e empacota por competencia em pasta/zip
  organizado. NAO envia nada — quem toca conector externo, sempre com gate
  humano, e a skill envio-contabilidade. Use quando o operador disser
  "montar pacote da contabilidade", "fechar o mes para o contador",
  "triagem contabil", "organizar documentos do mes", "preparar envio
  contabil", "o que mando pro contador", "/cfo-contabil".
---

# TRIAGEM-CONTABIL — Pacote Mensal para a Contabilidade

## 1. ESCOPO

Consolida tudo que a contabilidade precisa de uma entidade num periodo:
extratos, notas, estado de conciliacao, e um relatorio honesto de
pendencias. Empacota por competencia, pronto para revisao.

**Importante:** esta skill **monta** o pacote. Ela **NAO envia** — o envio
e exclusividade da `envio-contabilidade` (gate humano, trava 2). Aqui
o pacote fica disponivel localmente para envio manual ou para o operador
acionar o `/cfo-enviar`.

## 2. INPUT NECESSARIO

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `entidade_id` | sim | Entidade a empacotar — **PERGUNTAR** se ausente |
| `competencia` | sim | Mes (YYYY-MM) ou intervalo |
| `formato` | opcional | pasta organizada (default) ou zip |

Pre-requisito: extrato + notas ingeridos e `conciliacao-bancaria` rodada
na competencia. Se a conciliacao nao rodou → roda antes (ou avisa).

## 3. PROCESSAMENTO

### Passo 1 — Validar pre-requisitos

- Extratos da competencia ingeridos? Notas ingeridas? Conciliacao feita?
- Faltando algo → listar o que falta e oferecer rodar a camada A /
  `conciliacao-bancaria` antes de empacotar. Nao empacota pela metade
  sem avisar.

### Passo 2 — Selecionar conteudo da competencia

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lib/canonical.py --triagem \
  --entidade <entidade_id> --competencia <YYYY-MM> --formato <pasta|zip>
```

O engine seleciona do `base.sqlite`:
- Extratos/transacoes da competencia (com categoria e estado de
  conciliacao).
- Notas fiscais da competencia (entrada e saida).
- Mapa de conciliacao (conciliado × pendente).
- Os arquivos originais ingeridos, se ainda referenciados.

### Passo 3 — Gerar indice do pacote

Indice (`INDICE.md` ou `INDICE.txt`) listando:
- Entidade (nome + doc mascarado), competencia.
- Arquivos incluidos e o que cada um e.
- Totais: creditos, debitos, notas de entrada/saida, tributos destacados.
- Contagem conciliado × pendente.

### Passo 4 — Relatorio de pendencias

Bloco honesto do que **falta** ou **diverge** — herdado da
`conciliacao-bancaria`:
- Lancamentos sem nota / notas sem pagamento.
- Divergencias de valor.
- Possiveis duplicidades.
- Transferencias intragrupo marcadas (informar a contabilidade para
  tratamento correto).
- Transacoes ainda `a_classificar`.

A contabilidade precisa saber o que esta pendente antes de fechar — esse
relatorio e o que evita retrabalho.

### Passo 5 — Empacotar por competencia

Estrutura no workdir do operador (LGPD — fica em `.cfo/`, fora do git):

```
<cwd>/.cfo/entidades/{entidade_id}/triagem/{competencia}/
├── INDICE.md
├── RELATORIO-PENDENCIAS.md
├── extratos/            (originais + csv normalizado)
├── notas/               (XMLs)
└── conciliacao.csv      (conciliado x pendente)
```

(zip opcional do mesmo conteudo). Mascaramento de dado sensivel em
qualquer log gerado (trava 3).

## 4. OUTPUT

```markdown
## 📦 Pacote Contabil — {{entidade}} · {{competencia}}

**Local:** `<cwd>/.cfo/entidades/{{id}}/triagem/{{competencia}}/`
**Formato:** [pasta organizada] · **Pronto para envio:** sim

| Conteudo | Qtd |
|---|---:|
| Extratos | 3 contas |
| Notas fiscais | 37 |
| Transacoes conciliadas | 118 |
| Pendencias | 22 |

### Resumo financeiro da competencia
| Item | Valor |
|---|---:|
| Creditos | R$ ... |
| Debitos | R$ ... |
| Tributos destacados | R$ ... |

### ⚠️ Relatorio de pendencias (a contabilidade precisa saber)
- [22 itens pendentes — ver RELATORIO-PENDENCIAS.md]
- [11 transacoes ainda "a_classificar"]
- [4 transferencias intragrupo marcadas]

### Proximo passo
- Envio com gate humano: `/cfo-enviar` (NAO envio automatico — trava 2).
- Ou envie manualmente os arquivos da pasta acima.
```

## 5. PROIBICOES

1. **Nunca** enviar o pacote (envio = `envio-contabilidade`, gate humano).
2. **Nunca** empacotar pela metade sem avisar o que falta.
3. **Nunca** omitir o relatorio de pendencias para "parecer mais limpo".
4. **Nunca** gravar dado sensivel em log texto plano (mascarar — trava 3).
5. **Nunca** colocar o pacote fora de `.cfo/` (LGPD, fica fora do git).
6. **Nunca** propagar excecao de import ao Cowork (premortem C2).

## 6. INTEGRACAO

- **Upstream:** `conciliacao-bancaria`, camada A.
- **Downstream:** `envio-contabilidade` (`/cfo-enviar` — gate humano).
- **Auditoria:** `auditoria-cfo` R1/R4 (completude do pacote).
