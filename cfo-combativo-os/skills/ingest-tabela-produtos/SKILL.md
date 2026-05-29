---
name: ingest-tabela-produtos
description: >
  INGEST-TABELA-PRODUTOS — Le tabela de produtos/servicos e precos
  (XLSX ou CSV) e normaliza para o catalogo
  {sku, descricao, custo, preco_venda, margem, categoria} vinculado a uma
  entidade do grafo. Orquestra o parser de planilha local
  (scripts/parsers/xlsx_parser.py / csv_parser.py) com degradacao graciosa
  se pandas/openpyxl estiver ausente. Detecta colunas ausentes e PERGUNTA
  antes de supor — nunca preenche custo, preco ou margem por suposicao.
  Alimenta o benchmark de precos e a saude de margem. Use quando o
  operador disser "importar tabela de produtos", "carrega a planilha de
  precos", "subir catalogo", "ingerir lista de produtos", "minha tabela de
  precos", ou anexar/apontar planilha de produtos.
---

# INGEST-TABELA-PRODUTOS — Ingestao do Catalogo de Precos

## 1. ESCOPO

Le a tabela de produtos/servicos do operador e monta um catalogo
normalizado por entidade. Serve de insumo para `benchmark-precos`
(saude de margem, reprecificacao) e para o painel de margem do dashboard.

NAO precifica por conta propria, NAO pesquisa mercado aqui (isso e
`benchmark-precos`, e so com autorizacao), NAO inventa custo/preco que
nao esta na planilha (trava 4, PA-14).

## 2. INPUT NECESSARIO

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `arquivo_path` | sim | Caminho do XLSX/CSV |
| `entidade_id` | sim | A qual entidade o catalogo pertence — **PERGUNTAR** se ausente |
| `mapa_colunas` | derivado | Mapeamento coluna planilha → campo canonico |

## 3. PROCESSAMENTO

### Passo 1 — Resolver entidade

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-state.py --list-entidades
```

### Passo 2 — Ler a planilha

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parsers/xlsx_parser.py "<arquivo_path>" \
  --modo catalogo --entidade <entidade_id>
```

(CSV → `csv_parser.py --modo catalogo`). O parser:
- Tenta `pandas`/`openpyxl`; XLSX detecta cabecalho deslocado e
  linhas-lixo.
- **Fallback** `csv`/leitura minima (stdlib) quando possivel.
- Lib ausente e fallback impossivel → **declara** e instrui
  `pip install pandas openpyxl`. **NUNCA** crasha a sessao (premortem C2).
- Retorna as linhas + os cabecalhos detectados (stdout JSON).

### Passo 3 — Mapear colunas → schema do catalogo

Schema-alvo por produto:

```json
{
  "sku": "codigo do produto/servico",
  "descricao": "nome",
  "custo": 0.0,
  "preco_venda": 0.0,
  "margem": 0.0,
  "categoria": "linha/grupo do produto",
  "entidade_id": "empresa-alfa"
}
```

**REGRA DURA — PA-14 (nunca supor):**
- Detectar as colunas presentes na planilha.
- Se faltar `custo`, `preco_venda` ou `categoria`, **PERGUNTAR** ao
  operador qual coluna corresponde (ou se o dado nao existe).
  - Exemplo: *"Sua planilha tem `descricao` e `preco`, mas nao identifiquei
    a coluna de custo. Qual coluna e o custo? Ou prefere importar sem custo
    (margem ficara indisponivel)?"*
- **NUNCA** preencher custo/preco/margem com chute, media ou zero
  silencioso. Coluna ausente confirmada pelo operador → campo fica `null`
  e a margem dependente fica explicitamente `indisponivel`.
- `margem` so e calculada (`(preco_venda - custo) / preco_venda`) quando
  AMBOS custo e preco existem e sao validos. Caso contrario → `null`.

### Passo 4 — Persistencia

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lib/canonical.py --persist-catalogo \
  --entidade <entidade_id>
```

- Grava no `base.sqlite` da entidade (tabela de catalogo).
- Idempotencia por `sku` dentro da entidade (reimportar atualiza o item,
  nao duplica). Backup antes de salvar.

### Passo 5 — Relatorio

Resumir itens lidos, quantos com margem calculavel, quantos com dados
faltando (e quais campos), itens com margem negativa (sinalizar).

## 4. OUTPUT

```markdown
## 🏷️ Ingestao de Catalogo — {{entidade}}

**Itens lidos:** [128] · **Com margem calculavel:** [104]

| Situacao | Qtd |
|---|---:|
| Margem calculada | 104 |
| Sem custo (margem indisponivel) | 18 |
| Sem preco de venda | 6 |
| ⚠️ Margem negativa | 3 |

### Mapeamento de colunas confirmado
| Campo canonico | Coluna da planilha |
|---|---|
| sku | "Codigo" |
| descricao | "Produto" |
| custo | "Custo Unit" |
| preco_venda | "Preco" |
| categoria | "Linha" |

### ⚠️ Colunas ausentes (confirmadas com o operador)
- [nenhuma] / [coluna "custo" inexistente em 18 itens — margem nula]

> Para validar precos vs mercado e simular reprecificacao, use
> `benchmark-precos` (`/cfo-precos`).
```

## 5. DEGRADACAO GRACIOSA (premortem C2)

- `pandas`/`openpyxl` ausentes → fallback leitura minima → se impossivel,
  declara e instrui o `pip install`. Nada quebra.
- Cabecalho ambiguo → mostra as primeiras linhas e pede o mapeamento. Nao
  adivinha.

## 6. PROIBICOES

1. **Nunca** supor coluna ausente — sempre PERGUNTAR (PA-14, trava 4).
2. **Nunca** preencher custo/preco/margem com chute ou zero silencioso.
3. **Nunca** calcular margem sem custo E preco validos.
4. **Nunca** pesquisar mercado aqui (escopo de `benchmark-precos`, e so
   com autorizacao do operador).
5. **Nunca** propagar excecao de import ao Cowork (premortem C1/C2).
6. **Nunca** gravar catalogo sem entidade resolvida no grafo.

## 7. INTEGRACAO

- **Upstream:** `cfo-master`, `cfo-onboarding`.
- **Downstream:** `benchmark-precos` (saude de margem, reprecificacao),
  `dashboard-html` (painel de margem por produto).
- **Auditoria:** `auditoria-cfo` R1.
