---
name: ingest-notas-fiscais
description: >
  INGEST-NOTAS-FISCAIS — Le notas fiscais eletronicas (NF-e, NFC-e e
  NFS-e) em XML e normaliza itens, tributos destacados e contrapartes para
  a base local da entidade, vinculando cada nota a uma conta/entidade do
  grafo multi-entidade. Orquestra o parser Python local
  (scripts/parsers/nfe_parser.py) com degradacao graciosa se a lib nfelib
  estiver ausente (fallback xml.etree). Alimenta carga-tributaria e a
  conciliacao bancaria. Use quando o operador disser "importar nota
  fiscal", "le esse XML de NF-e", "carrega as notas do mes", "ingerir
  NFS-e", "subir nota do servico", "/cfo-ingest", ou anexar/apontar XML
  de nota fiscal.
---

# INGEST-NOTAS-FISCAIS — Ingestao de NF-e / NFC-e / NFS-e

## 1. ESCOPO

Le o XML da nota fiscal, extrai itens + tributos + contraparte, normaliza
e grava na base da entidade. Serve de matriz documental para a
**conciliacao** (casar nota × pagamento) e para a **carga-tributaria**
(consolidar tributos destacados).

NAO calcula tributo devido, NAO faz planejamento tributario (handoff ao
`tributario-societario-adv-os` — compartimentacao §11), NAO inventa
valor que nao esta na nota (trava 4).

## 2. INPUT NECESSARIO

| Campo | Obrigatorio | Observacoes |
|---|---|---|
| `arquivo_path` | sim | Caminho do XML (NF-e/NFC-e/NFS-e) ou pasta com varios |
| `entidade_id` | sim | A qual entidade a nota pertence — **PERGUNTAR** se ausente |
| `papel` | derivado | emitente (saida/receita) ou destinatario (entrada/custo) |
| `municipio` | NFS-e | Layout NFS-e varia por municipio (ABRASF/padrao nacional) |

**Regra dura:** nota sempre vinculada a uma entidade do grafo. Resolver o
papel (emitente = receita; destinatario = custo/entrada) a partir do
CNPJ da entidade vs CNPJ na nota. Se a entidade nao existe no grafo →
`/cfo-setup` primeiro.

## 3. PROCESSAMENTO

### Passo 1 — Resolver entidade no grafo

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-state.py --list-entidades
```

### Passo 2 — Chamar o parser

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parsers/nfe_parser.py "<arquivo_path>" \
  --entidade <entidade_id>
```

O parser:
- Tenta `nfelib` (bindings oficiais Fazenda) para NF-e/NFC-e.
- NFS-e: tenta layout ABRASF + padrao nacional; por municipio quando
  necessario (operador informa o municipio se layout nao reconhecido).
- **Fallback `xml.etree`** (stdlib) se `nfelib` ausente — extrai os campos
  essenciais por XPath.
- Se nem o fallback funciona → **declara** e instrui `pip install nfelib`.
  **NUNCA** propaga excecao (premortem C2). Sessao do Cowork nao quebra.
- Retorna estrutura por nota (stdout JSON).

### Passo 3 — Estrutura extraida por nota

```json
{
  "chave": "44 digitos (mascarada em log)",
  "tipo": "nfe|nfce|nfse",
  "data_emissao": "YYYY-MM-DD", "competencia": "YYYY-MM",
  "papel": "emitente|destinatario",
  "emitente": "nome/CNPJ mascarado", "destinatario": "nome/CNPJ mascarado",
  "valor_total": 0.0,
  "itens": [{"descricao":"", "ncm_ou_servico":"", "qtd":0, "valor_unit":0.0, "cfop":""}],
  "tributos": {"icms":0.0,"iss":0.0,"pis":0.0,"cofins":0.0,"ipi":0.0},
  "entidade_id": "empresa-alfa"
}
```

### Passo 4 — Persistencia append-only

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lib/canonical.py --persist-notas \
  --entidade <entidade_id>
```

- Grava na `base.sqlite` da entidade (tabela de notas).
- Idempotencia pela **chave da nota** (reimportar a mesma nota nao
  duplica). Append-only por competencia (§2.4) — backup antes de salvar.

### Passo 5 — Relatorio

Resumir notas lidas, total faturado (emitente) / total de entradas
(destinatario), e tributos destacados consolidados por competencia.

## 4. OUTPUT

```markdown
## 📄 Ingestao de Notas — {{entidade}}

**Competencia:** [2026-04] · **Notas lidas:** [37]

| Tipo | Qtd | Valor total |
|---|---:|---:|
| NF-e (saida) | 22 | R$ ... |
| NF-e (entrada) | 10 | R$ ... |
| NFS-e | 5 | R$ ... |

### Tributos destacados (informativo)
| Tributo | Total no periodo |
|---|---:|
| ICMS | R$ ... |
| ISS | R$ ... |
| PIS/COFINS | R$ ... |
| IPI | R$ ... |

### Modo de leitura
- Lib usada: [nfelib] (ou: fallback xml.etree)

> Consolidacao tributaria e **informativa** (alimenta carga-tributaria).
> Planejamento tributario formal = assessoria especializada (handoff).
```

## 5. DEGRADACAO GRACIOSA (premortem C2)

- `nfelib` ausente → fallback `xml.etree` extrai o essencial.
- Fallback impossivel → declara, instrui `pip install nfelib`, nada se
  perde. Nunca crashar.
- Layout NFS-e municipal desconhecido → mostra a arvore do XML e pede
  confirmacao dos campos. Nao adivinha valor.

## 6. PROIBICOES

1. **Nunca** inventar item, valor ou tributo ausente na nota (trava 4).
2. **Nunca** calcular tributo devido ou fazer planejamento (handoff).
3. **Nunca** registrar chave/CNPJ completo em log texto plano (mascarar).
4. **Nunca** propagar excecao de import ao Cowork (premortem C1/C2).
5. **Nunca** gravar nota sem entidade resolvida no grafo.
6. **Nunca** tratar tributos vigentes em 2026 como extintos (Reforma e
   gradual 2027-2032 — quem trata disso e `carga-tributaria`).

## 7. INTEGRACAO

- **Upstream:** `cfo-master`, `cfo-onboarding`.
- **Downstream:** `carga-tributaria` (consolida tributos), 
  `conciliacao-bancaria` (casa nota × pagamento).
- **Auditoria:** `auditoria-cfo` R1.
- **Handoff:** `tributario-societario-adv-os` para parecer/regime.
