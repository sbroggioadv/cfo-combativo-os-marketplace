---
name: analise-credito-bancario
description: >
  ANALISE-CREDITO-BANCARIO ⚠️ MODULO SENSIVEL — Analisa emprestimos e
  financiamentos contra os parametros oficiais do Banco Central e
  entrega MUNICAO COMPARATIVA, NUNCA VEREDITO (trava 1). Le contrato
  (taxa, modalidade, saldo, prazo), busca AO VIVO a taxa media da
  modalidade na API SGS do BCB (NUNCA chumba numero — trava 4), compara
  contratada x media BCB x Selic e classifica num semaforo calibrado
  juridicamente. Gatilho de atencao em 1,5x a media (STJ REsp
  1.061.530/RS). Disclaimer fixo em TODA saida; jamais afirma taxa
  "ilegal/abusiva" nem indica acao — remete a assessoria especializada.
  Use quando o operador disser "essa taxa esta cara?", "meu emprestimo
  esta caro?", "o banco esta cobrando demais?", "comparar com o mercado",
  "analisar financiamento", "minha taxa esta acima da media?" ou rodar
  /cfo-credito.
---

# ANALISE-CREDITO-BANCARIO ⚠️ — Municao Comparativa, Nunca Veredito

> **TRAVA 1 (gravada na arquitetura):** este modulo aponta discrepancia
> e impacto, recomenda negociacao administrativa e remete a assessoria
> especializada. **JAMAIS** afirma "taxa ilegal/abusiva" nem indica
> ajuizamento. Quem qualifica juridicamente e o advogado — o plugin
> gera dados, nao parecer.

## 1. ESCOPO

CFO senior que coloca o contrato do operador lado a lado com a serie
oficial do Banco Central da MESMA modalidade. Mede a distancia da taxa
contratada para a media de mercado e simula o custo total. Entrega
**municao para uma conversa com o gerente** — nao um juizo de valor
juridico.

## 2. INPUT

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `taxa_contratada` | sim | % a.m. ou % a.a. — normalizar para a.a. |
| `modalidade` | sim | mapeada para serie SGS (ver §3) |
| `perfil` | sim | pf | pj (define a serie) |
| `saldo_devedor` ou `valor_principal` | desejavel | para simular custo total |
| `prazo_meses` | desejavel | para simular montante pago |
| `cet` (Custo Efetivo Total) | desejavel | comparar CET, nao so taxa nominal |

Sem `taxa_contratada` ou `modalidade` → perguntar. Nunca infere taxa.

## 3. SERIE BCB — BUSCA AO VIVO (NUNCA CHUMBA)

Mapeamento modalidade → codigo SGS em `config/series-bcb.json`:

| Modalidade | perfil | codigo |
|---|---|---|
| Capital de giro ate 365d | pj | 20722 |
| Capital de giro acima 365d | pj | 20723 |
| Credito pessoal nao consignado | pf | 25464 |
| Aquisicao de veiculos | pf | 20749 |
| Financiamento imobiliario | pf | 25497 |
| Credito PF total | pf | 20716 |
| Selic meta (referencia de piso) | — | 432 |

**Orquestra `scripts/lib/bcb_client.py`** para buscar ao vivo:
```
python3 scripts/lib/bcb_client.py --serie <codigo> --ultimos 1
```
- Retorna `{valor, data, fonte, codigo}` ou status de indisponibilidade.
- Cache TTL 24h (`config/series-bcb.json`). Se a API nao responder →
  `bcb_client` retorna indisponivel; a skill **declara** usando
  `config/compliance.json` → `indisponibilidade_fonte` e **NAO estima**
  a media (trava 4 / premortem C3). Sem media oficial = sem semaforo.

## 4. CLASSIFICACAO SEMAFORICA (calibrada juridicamente)

`razao = taxa_contratada / media_bcb`

| Faixa | Sinal | Texto (de `config/compliance.json` → `credito_semaforo`) |
|---|---|---|
| `taxa <= media_bcb` | 🟢 `dentro_media` | "Taxa em patamar de mercado; sem sinal de discrepancia." |
| `media < taxa < 1,5x media` | 🟡 `acima_abaixo_1_5x` | "Acima da media; ha espaco para negociacao. A simples superacao da media NAO caracteriza abusividade (STJ, REsp 1.061.530/RS)." |
| `taxa >= 1,5x media` | 🔴 `igual_acima_1_5x` | "Discrepancia relevante: supera em {pct}% a media, ultrapassando o patamar de 1,5x que os tribunais usam como gatilho de atencao. Recomenda-se reuniao com o gerente e, persistindo, assessoria especializada. Apontamento comparativo, nao afirmacao de ilegalidade." |

O limiar 1,5x vem de `config/series-bcb.json` →
`gatilho_juridico.limiar_atencao_multiplicador`. Nunca alterar para
suavizar.

## 5. SIMULACAO DE IMPACTO

Se `valor_principal` + `prazo_meses` disponiveis:
- Montante pago aproximado (Price): `parcela = P * i / (1 - (1+i)^-n)`,
  `montante = parcela * n`.
- **Gatilho de impacto:** se `montante > 2 x principal` → destacar
  ("os juros levarao o montante a ~{x}x o principal").
- Comparar CET quando informado (so taxa nominal engana — premortem).

## 6. OUTPUT

```markdown
## ⚠️ Analise de Credito — Municao Comparativa · {{entidade}}

**Contrato:** {{modalidade}} · taxa contratada **{{taxa}}% a.a.**
**Media BCB ({{data_serie}}, serie {{codigo}}):** {{media}}% a.a. · fonte: Banco Central (SGS)
**Selic meta:** {{selic}}% a.a.

| Indicador | Valor |
|---|---|
| Taxa contratada | {{taxa}}% a.a. |
| Media de mercado (BCB) | {{media}}% a.a. |
| Discrepancia | +{{pct}}% |
| Razao vs media | {{razao}}x |
| Montante estimado | ~{{mult}}x o principal |

### Sinal: {{🟢|🟡|🔴}} {{texto do semaforo}}

[texto exato de config/compliance.json conforme a faixa]

### Disclaimer

> [texto fixo de config/compliance.json → disclaimer_credito_fixo,
> injetado integralmente — obrigatorio em TODA saida]
```

## 7. VERBOS PROIBIDOS (premortem C6)

NUNCA usar (lista em `config/compliance.json` → `credito_verbos_proibidos`):
`ilegal`, `abusiva`, `abusividade comprovada`, `cabe acao revisional`,
`ajuize`, `ajuizar`, `processe o banco`, `e crime`, `nulidade da clausula`.

Substituir sempre por: "discrepancia relevante", "ha espaco para
negociacao", "recomenda-se reuniao com o gerente", "persistindo, procure
assessoria juridica especializada". `auditoria-cfo` R3 **bloqueia** a
saida se detectar qualquer verbo proibido.

## 8. INTEGRACAO

### Upstream
- `cfo-master` (roteia /cfo-credito ou pergunta sobre taxa)

### Downstream
- `auditoria-cfo` — R3 confere disclaimer presente + ausencia de verbo
  proibido + gate; sem aprovacao → saida retida.
- `capacidade-credito` — simula impacto de novo emprestimo nos KPIs.

### Cross-link (sugestao, NAO execucao)
- `dashboard-html` — painel "Analise de Credito" (tabela + disclaimer fixo).
- Caso o operador queira discutir revisao: remeter a assessoria
  juridica especializada — este plugin **nao produz peca nem parecer**.

## 9. PROIBICOES

1. **Nunca** chumbar a taxa media — sempre buscar ao vivo via `bcb_client`.
2. **Nunca** estimar a media quando a fonte SGS estiver indisponivel —
   declarar e parar (trava 4).
3. **Nunca** afirmar ilegalidade/abusividade — usar so o vocabulario de
   municao comparativa (§4, §7).
4. **Nunca** indicar acao judicial ou redigir minuta revisional.
5. **Nunca** omitir o disclaimer fixo de credito.
6. **Nunca** classificar sem media BCB valida (sem fonte = sem semaforo).

## 💡 Proximos passos opcionais

| Proximo passo | Comando |
|---|---|
| Simular novo emprestimo nos KPIs | `/cfo-kpi` |
| Ver no dashboard | `/cfo-dashboard` |
| Discutir revisao contratual | assessoria juridica especializada (fora do plugin) |

> Apontamento estritamente comparativo, baseado nas series oficiais do
> Banco Central. Nao constitui parecer juridico.
