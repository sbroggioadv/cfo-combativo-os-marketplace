---
name: ingest-extrato-bancario
description: >
  INGEST-EXTRATO-BANCARIO — Le extratos bancarios e de cartao (OFX/QFX,
  CSV multi-banco, XLSX) e normaliza tudo para o schema canonico de
  transacao, vinculando cada lancamento a uma conta e entidade do grafo
  multi-entidade. Orquestra os parsers Python locais
  (scripts/parsers/ofx_parser.py, csv_parser.py, xlsx_parser.py) com
  degradacao graciosa se a lib estiver ausente. Persistencia append-only
  por competencia (reprocessar um mes substitui so aquele mes). Use quando
  o operador disser "importar extrato", "le esse OFX", "carrega o CSV do
  Itau/Nubank/Inter", "ingerir extrato bancario", "subir movimentacao do
  cartao", "/cfo-ingest", ou anexar/apontar arquivo de extrato.
---

# INGEST-EXTRATO-BANCARIO — Ingestao de Extratos ao Grafo

## 1. ESCOPO

Porta de entrada dos dados de movimentacao. Le extrato bruto (banco ou
cartao), normaliza ao **schema canonico §3** e grava no `base.sqlite` da
entidade dona da conta. Tudo local — nada sai da maquina (trava 3).

NAO classifica juridicamente, NAO concilia (isso e `conciliacao-bancaria`),
NAO inventa transacao que nao esta no arquivo (trava 4).

## 2. INPUT NECESSARIO

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `arquivo_path` | sim | Caminho do OFX/QFX/CSV/XLSX |
| `conta_id` | sim | A qual conta do grafo pertence — **PERGUNTAR** se nao informado |
| `entidade_id` | derivado | Resolve-se da conta no `cfo-state.json` |
| `banco` | derivado/perguntar | Para CSV/XLSX: define layout de leitura |

**Regra dura:** todo lancamento precisa de `entidade_id`+`conta_id`. Se o
operador nao disser a qual conta o arquivo pertence, **PERGUNTE** listando
as contas do grafo. Nunca adivinhe. Se a conta nao existe no grafo →
roteia para `cfo-onboarding` (`/cfo-setup`) para cadastrar antes.

## 3. PROCESSAMENTO

### Passo 1 — Resolver entidade/conta no grafo

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-state.py --list-contas
```

Mostra contas disponiveis (entidade → contas). Operador escolhe o
`conta_id`. Se vazio → cadastrar via `/cfo-setup` primeiro.

### Passo 2 — Detectar formato e chamar o parser certo

| Extensao | Parser | Lib primaria | Fallback |
|---|---|---|---|
| `.ofx` `.qfx` | `ofx_parser.py` | `ofxparse` | `xml.etree` (stdlib) |
| `.csv` | `csv_parser.py` | auto-layout banco | `csv` (stdlib) |
| `.xlsx` `.xls` | `xlsx_parser.py` | `pandas`/`openpyxl` | declarar + instruir |

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parsers/ofx_parser.py "<arquivo_path>" \
  --entidade <entidade_id> --conta <conta_id>
```

(troque pelo parser correspondente ao formato). O parser:
- Tenta a lib → se ausente, cai no fallback stdlib
- Se nem o fallback funciona → **declara** e instrui `pip install ofxparse`
  (ou `pandas openpyxl`). **NUNCA** propaga excecao — degradacao graciosa
  obrigatoria (premortem C2). A sessao do Cowork nao pode quebrar.
- CSV: auto-detecta layout por banco (Itau/BB/Bradesco/Santander/Nubank/
  Inter/C6/Caixa). Mapeamento aprendido salvo por banco para reuso.
- XLSX: detecta cabecalho deslocado e linhas-lixo antes de mapear.
- Retorna lista de transacoes em **schema canonico §3** (stdout JSON).

### Passo 3 — Normalizacao ao schema canonico

Cada transacao DEVE sair assim (parser ja entrega; a skill confere):

```json
{
  "id": "sha256(entidade+conta+data+valor+descricao)",
  "entidade_id": "empresa-alfa",
  "conta_id": "itau-cc-001",
  "data": "2026-04-12", "competencia": "2026-04",
  "valor": 1234.56, "sinal": "C|D",
  "descricao": "texto bruto", "categoria": "auto ou a_classificar",
  "contraparte": "inferido (mascarado em log)",
  "doc_vinculado": null, "banco": "itau",
  "origem": "ofx|csv|xlsx", "is_transferencia_intragrupo": false
}
```

Categoria sai da heuristica de `config/categorias.json`; sem match
confiavel → `a_classificar` (nunca chute). `is_transferencia_intragrupo`
fica `false` aqui — quem seta e a `conciliacao-bancaria` (premortem C7).

### Passo 4 — Persistencia append-only por competencia

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lib/canonical.py --persist \
  --entidade <entidade_id> --conta <conta_id>
```

- Grava no `<cwd>/.cfo/entidades/{entidade_id}/base.sqlite`.
- **Idempotencia por `(entidade, conta, competencia)`** (§2.4): reprocessar
  abril **substitui so abril daquela conta** — jamais faz rebuild
  destrutivo do historico inteiro (premortem C8).
- Dedup por hash `id`: a mesma transacao reimportada nao duplica.
- `state.py` faz **backup** do estado antes de qualquer escrita.
- Adicionar uma conta/entidade nova nao invalida o ja consolidado.

### Passo 5 — Relatorio de ingestao

Resumir o que entrou. Apontar buracos de periodo (dias sem lancamento que
parecem suspeitos), transacoes `a_classificar`, e saldo de abertura/
fechamento se o arquivo trouxe.

## 4. OUTPUT

```markdown
## 📥 Ingestao — {{entidade}} / conta {{conta_apelido}}

**Arquivo:** [nome] · **Formato:** [OFX] · **Banco:** [itau]
**Periodo:** [01/04/2026 a 30/04/2026] · **Competencia:** [2026-04]

| Metrica | Valor |
|---|---:|
| Transacoes lidas | 142 |
| Creditos (C) | R$ ... |
| Debitos (D) | R$ ... |
| Novas (gravadas) | 138 |
| Duplicadas (dedup) | 4 |
| A classificar | 11 |

### Modo de leitura
- Lib usada: [ofxparse] (ou: fallback stdlib xml.etree)
- Layout CSV: [Nubank detectado e salvo]

### ⚠️ Pontos de atencao
- [11 transacoes ficaram em "a_classificar" — confirme categoria]
- [buraco de periodo 13-15/04 sem lancamento — confirmar]
```

## 5. DEGRADACAO GRACIOSA (premortem C2 — obrigatorio)

- Lib ausente → fallback stdlib → se impossivel, **declara**:
  *"Nao consegui ler [.xlsx]: a biblioteca pandas/openpyxl nao esta
  instalada. Rode `pip install pandas openpyxl` e reimporte. Nada foi
  perdido."* Nunca crashar a sessao.
- Arquivo corrompido/layout irreconhecivel → mostra amostra das linhas e
  pede o mapeamento de colunas ao operador. Nao adivinha.

## 6. PROIBICOES

1. **Nunca** gravar transacao sem `entidade_id`+`conta_id` resolvidos.
2. **Nunca** inventar transacao, valor, data ou contraparte (trava 4).
3. **Nunca** fazer rebuild destrutivo do historico (so substitui a
   competencia reprocessada).
4. **Nunca** registrar conta/CPF/CNPJ/saldo em texto plano no log
   (mascarar — trava 3).
5. **Nunca** propagar excecao de import para o Cowork (premortem C1/C2).
6. **Nunca** classificar com falsa confianca — em duvida, `a_classificar`.

## 7. INTEGRACAO

- **Upstream:** `cfo-master`, `cfo-onboarding` (grafo pronto).
- **Downstream:** `conciliacao-bancaria`, `fluxo-de-caixa`,
  `indicadores-kpi`, `deteccao-anomalias`.
- **Auditoria:** `auditoria-cfo` R1 (integridade de dados).
