#!/usr/bin/env python3
"""
canonical.py — Schema canonico de transacao (design-spec §3) + persistencia
SQLite APPEND-ONLY por competencia (design-spec §2.4 / premortem C8).

Responsabilidades:
- Transacao: dataclass do schema canonico §3.
- normalizar(): qualquer dict de parser -> transacao canonica validada.
- tx_hash(): dedup idempotente por sha256 de (entidade+conta+data+valor+descricao).
- CanonicalStore: SQLite por entidade (<workdir>/.cfo/entidades/{id}/base.sqlite).
    - ingest_competencia(): grava as transacoes de UM mes de UMA conta.
      Idempotente por (entidade, conta, competencia): reprocessar substitui
      SO aquele mes daquela conta — NUNCA rebuild destrutivo do historico.
- Recortes: por entidade, por grupo (elimina is_transferencia_intragrupo),
  total consolidado.

REGRA DURA (premortem C8): adicionar/reingerir nunca apaga meses ou entidades
que ja existem. O DELETE de ingest e cirurgico — so a chave (entidade, conta,
competencia) que esta sendo reprocessada.

Stdlib only (sqlite3, hashlib, json) — sem dependencia externa.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

STATE_DIR = ".cfo"
SINAIS = ("C", "D")
ORIGENS = ("ofx", "csv", "xlsx", "nfe", "manual")


# ---------------------------------------------------------------------------
# Schema canonico (design-spec §3)
# ---------------------------------------------------------------------------

@dataclass
class Transacao:
    entidade_id: str
    conta_id: str
    data: str                 # YYYY-MM-DD
    valor: float
    sinal: str                # "C" | "D"
    descricao: str
    competencia: str = ""     # YYYY-MM (derivada da data se vazia)
    categoria: str = "a_classificar"
    contraparte: str | None = None
    doc_vinculado: str | None = None
    banco: str | None = None
    origem: str = "manual"
    is_transferencia_intragrupo: bool = False
    id: str = ""              # hash sha256 (preenchido em __post_init__)
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # competencia derivada da data se nao informada
        if not self.competencia and self.data and len(self.data) >= 7:
            self.competencia = self.data[:7]
        # valor sempre positivo; o sentido vive em `sinal`
        try:
            self.valor = round(abs(float(self.valor)), 2)
        except (TypeError, ValueError):
            self.valor = 0.0
        if self.sinal not in SINAIS:
            self.sinal = "D" if str(self.sinal).upper().startswith(("D", "-")) else "C"
        if not self.id:
            self.id = tx_hash(self.entidade_id, self.conta_id, self.data,
                              self.valor, self.descricao)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tx_hash(entidade_id: str, conta_id: str, data: str,
            valor: float, descricao: str) -> str:
    """Hash sha256 idempotente de (entidade+conta+data+valor+descricao).

    Normaliza valor para 2 casas e descricao para uppercase-strip-collapse,
    garantindo que a MESMA transacao reingerida gere o MESMO id (dedup).
    """
    desc_norm = " ".join(str(descricao).upper().split())
    base = f"{entidade_id}|{conta_id}|{data}|{abs(round(float(valor or 0), 2)):.2f}|{desc_norm}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def normalizar(raw: dict[str, Any], *, entidade_id: str, conta_id: str,
               origem: str = "manual", banco: str | None = None) -> Transacao:
    """Converte um dict cru de parser para Transacao canonica.

    Aceita variacoes de chave comuns (data/date, valor/amount, etc) e
    degrada graciosamente: campo ausente vira default, nunca quebra.
    """
    def _get(*keys, default=None):
        for k in keys:
            if k in raw and raw[k] not in (None, ""):
                return raw[k]
        return default

    data = str(_get("data", "date", "dt", default="") or "")
    # normaliza DD/MM/YYYY -> YYYY-MM-DD se vier no formato BR
    if "/" in data and len(data) == 10:
        d, m, y = data.split("/")
        data = f"{y}-{m}-{d}"

    valor_raw = _get("valor", "amount", "value", default=0)
    sinal = _get("sinal", "sign", default=None)
    if sinal is None:
        # infere pelo sinal do numero
        try:
            sinal = "D" if float(str(valor_raw).replace(",", ".")) < 0 else "C"
        except (TypeError, ValueError):
            sinal = "C"

    if isinstance(valor_raw, str):
        valor_raw = valor_raw.replace(".", "").replace(",", ".") if "," in valor_raw else valor_raw

    if origem not in ORIGENS:
        origem = "manual"

    return Transacao(
        entidade_id=entidade_id,
        conta_id=conta_id,
        data=data,
        valor=valor_raw,
        sinal=str(sinal).upper()[:1] if sinal else "C",
        descricao=str(_get("descricao", "description", "memo", "historico", default="")),
        competencia=str(_get("competencia", default="") or ""),
        categoria=str(_get("categoria", "category", default="a_classificar")),
        contraparte=_get("contraparte", "counterparty", "payee"),
        doc_vinculado=_get("doc_vinculado", "nfe_chave", "fitid"),
        banco=banco or _get("banco", "bank"),
        origem=origem,
        is_transferencia_intragrupo=bool(_get("is_transferencia_intragrupo", default=False)),
    )


def dedup(transacoes: Iterable[Transacao]) -> list[Transacao]:
    """Remove duplicatas pelo id (hash). Mantem a primeira ocorrencia."""
    vistos: set[str] = set()
    out: list[Transacao] = []
    for tx in transacoes:
        if tx.id in vistos:
            continue
        vistos.add(tx.id)
        out.append(tx)
    return out


# ---------------------------------------------------------------------------
# Persistencia SQLite APPEND-ONLY por competencia (premortem C8)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transacoes (
    id TEXT PRIMARY KEY,
    entidade_id TEXT NOT NULL,
    conta_id TEXT NOT NULL,
    data TEXT NOT NULL,
    competencia TEXT NOT NULL,
    valor REAL NOT NULL,
    sinal TEXT NOT NULL,
    descricao TEXT,
    categoria TEXT,
    contraparte TEXT,
    doc_vinculado TEXT,
    banco TEXT,
    origem TEXT,
    is_transferencia_intragrupo INTEGER DEFAULT 0,
    extra TEXT
);
CREATE INDEX IF NOT EXISTS idx_competencia ON transacoes (competencia);
CREATE INDEX IF NOT EXISTS idx_conta_comp ON transacoes (conta_id, competencia);

CREATE TABLE IF NOT EXISTS ingest_log (
    entidade_id TEXT NOT NULL,
    conta_id TEXT NOT NULL,
    competencia TEXT NOT NULL,
    qtd INTEGER NOT NULL,
    ingerido_em TEXT NOT NULL,
    PRIMARY KEY (entidade_id, conta_id, competencia)
);
"""


class CanonicalStore:
    """SQLite por entidade. Append-only por (entidade, conta, competencia)."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    @classmethod
    def for_entidade(cls, workdir: Path, entidade_id: str) -> "CanonicalStore":
        db = Path(workdir) / STATE_DIR / "entidades" / entidade_id / "base.sqlite"
        return cls(db)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "CanonicalStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def ingest_competencia(self, conta_id: str, competencia: str,
                           transacoes: list[Transacao], *,
                           entidade_id: str | None = None) -> dict[str, Any]:
        """Grava as transacoes de UM mes de UMA conta.

        IDEMPOTENTE por (entidade, conta, competencia): apaga SO os registros
        daquela chave e regrava. NUNCA toca outras competencias/contas/entidades
        (premortem C8). Roda em transacao atomica.
        """
        if not transacoes:
            return {"ok": True, "ingeridas": 0, "competencia": competencia,
                    "conta_id": conta_id, "aviso": "nenhuma transacao a ingerir"}

        ent_id = entidade_id or transacoes[0].entidade_id
        # garante consistencia: so transacoes daquela conta/competencia
        alvo = [t for t in transacoes
                if t.conta_id == conta_id and t.competencia == competencia]
        alvo = dedup(alvo)

        import datetime as dt
        agora = dt.datetime.now(dt.timezone.utc).isoformat()

        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN")
            # DELETE cirurgico — SO esta chave
            cur.execute(
                "DELETE FROM transacoes WHERE conta_id = ? AND competencia = ?",
                (conta_id, competencia),
            )
            cur.executemany(
                """INSERT OR REPLACE INTO transacoes
                   (id, entidade_id, conta_id, data, competencia, valor, sinal,
                    descricao, categoria, contraparte, doc_vinculado, banco,
                    origem, is_transferencia_intragrupo, extra)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(t.id, ent_id, t.conta_id, t.data, t.competencia, t.valor, t.sinal,
                  t.descricao, t.categoria, t.contraparte, t.doc_vinculado, t.banco,
                  t.origem, 1 if t.is_transferencia_intragrupo else 0,
                  json.dumps(t.extra, ensure_ascii=False)) for t in alvo],
            )
            cur.execute(
                """INSERT OR REPLACE INTO ingest_log
                   (entidade_id, conta_id, competencia, qtd, ingerido_em)
                   VALUES (?,?,?,?,?)""",
                (ent_id, conta_id, competencia, len(alvo), agora),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return {"ok": True, "ingeridas": len(alvo), "competencia": competencia,
                "conta_id": conta_id, "entidade_id": ent_id}

    def competencias(self) -> list[str]:
        cur = self._conn.execute(
            "SELECT DISTINCT competencia FROM transacoes ORDER BY competencia"
        )
        return [r[0] for r in cur.fetchall()]

    def _rows(self, where: str = "", params: tuple = ()) -> list[dict]:
        sql = "SELECT * FROM transacoes"
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY data"
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def recorte_entidade(self, competencia: str | None = None,
                         *, incluir_intragrupo: bool = True) -> dict[str, Any]:
        """Visao individual da entidade (design-spec §2.3 recorte 1)."""
        where, params = [], []
        if competencia:
            where.append("competencia = ?")
            params.append(competencia)
        if not incluir_intragrupo:
            where.append("is_transferencia_intragrupo = 0")
        rows = self._rows(" AND ".join(where), tuple(params))
        return _agregar(rows)


def recorte_grupo(stores: dict[str, CanonicalStore], entidade_ids: list[str],
                  competencia: str | None = None) -> dict[str, Any]:
    """Soma das entidades do grupo ELIMINANDO transferencias intragrupo
    (design-spec §2.3 recorte 2 / premortem C7).
    """
    rows: list[dict] = []
    for eid in entidade_ids:
        st = stores.get(eid)
        if not st:
            continue
        where, params = ["is_transferencia_intragrupo = 0"], []
        if competencia:
            where.append("competencia = ?")
            params.append(competencia)
        rows.extend(st._rows(" AND ".join(where), tuple(params)))
    res = _agregar(rows)
    res["entidades_no_recorte"] = entidade_ids
    res["intragrupo_eliminado"] = True
    return res


def recorte_total(stores: dict[str, CanonicalStore],
                  competencia: str | None = None) -> dict[str, Any]:
    """Total consolidado de TODAS as entidades, fronteira PF/PJ explicita
    (design-spec §2.3 recorte 3). Intragrupo tambem eliminado no consolidado.
    """
    rows: list[dict] = []
    por_entidade: dict[str, dict] = {}
    for eid, st in stores.items():
        where, params = ["is_transferencia_intragrupo = 0"], []
        if competencia:
            where.append("competencia = ?")
            params.append(competencia)
        ent_rows = st._rows(" AND ".join(where), tuple(params))
        rows.extend(ent_rows)
        por_entidade[eid] = _agregar(ent_rows)
    res = _agregar(rows)
    res["por_entidade"] = por_entidade
    res["intragrupo_eliminado"] = True
    return res


def _agregar(rows: list[dict]) -> dict[str, Any]:
    creditos = sum(r["valor"] for r in rows if r["sinal"] == "C")
    debitos = sum(r["valor"] for r in rows if r["sinal"] == "D")
    return {
        "qtd_transacoes": len(rows),
        "total_creditos": round(creditos, 2),
        "total_debitos": round(debitos, 2),
        "saldo_periodo": round(creditos - debitos, 2),
        "transacoes": rows,
    }


# ---------------------------------------------------------------------------
# Auto-teste (dado SINTETICO — premortem C8: reingerir nao destroi historico)
# ---------------------------------------------------------------------------

def _auto_teste() -> int:
    import tempfile
    print("== AUTO-TESTE canonical.py (dado sintetico) ==")
    falhas = 0
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)

        # 1. hash idempotente
        h1 = tx_hash("alfa", "itau-001", "2026-04-10", 1500.0, "Pagamento Fornecedor X")
        h2 = tx_hash("alfa", "itau-001", "2026-04-10", 1500.00, "pagamento   fornecedor x")
        assert h1 == h2, "hash deveria ser idempotente (case/espaco/casas)"
        print("  [ok] tx_hash idempotente")

        # 2. normalizar dado cru com formato BR
        tx = normalizar({"data": "10/04/2026", "valor": "1.234,56", "descricao": "Venda"},
                        entidade_id="alfa", conta_id="itau-001", origem="csv", banco="itau")
        assert tx.data == "2026-04-10" and tx.valor == 1234.56 and tx.competencia == "2026-04"
        print("  [ok] normalizar formato BR -> canonico")

        store = CanonicalStore.for_entidade(wd, "alfa")

        # 3. ingerir abril
        abril = [
            normalizar({"data": "2026-04-05", "valor": 5000, "sinal": "C", "descricao": "Receita A"},
                       entidade_id="alfa", conta_id="itau-001", origem="ofx"),
            normalizar({"data": "2026-04-12", "valor": 1200, "sinal": "D", "descricao": "Aluguel"},
                       entidade_id="alfa", conta_id="itau-001", origem="ofx"),
        ]
        store.ingest_competencia("itau-001", "2026-04", abril)

        # 4. ingerir maio (NAO apaga abril — premortem C8)
        maio = [normalizar({"data": "2026-05-03", "valor": 800, "sinal": "D", "descricao": "Energia"},
                           entidade_id="alfa", conta_id="itau-001", origem="ofx")]
        store.ingest_competencia("itau-001", "2026-05", maio)
        assert set(store.competencias()) == {"2026-04", "2026-05"}, "maio apagou abril!"
        print("  [ok] ingerir maio preservou abril (append-only)")

        # 5. REINGERIR abril (corrigido) substitui SO abril, mantem maio
        abril_corrigido = [
            normalizar({"data": "2026-04-05", "valor": 5500, "sinal": "C", "descricao": "Receita A corrigida"},
                       entidade_id="alfa", conta_id="itau-001", origem="ofx"),
        ]
        store.ingest_competencia("itau-001", "2026-04", abril_corrigido)
        rec_abr = store.recorte_entidade("2026-04")
        rec_mai = store.recorte_entidade("2026-05")
        assert rec_abr["total_creditos"] == 5500 and rec_abr["qtd_transacoes"] == 1, "reingest abril errado"
        assert rec_mai["qtd_transacoes"] == 1, "reingest abril destruiu maio (premortem C8 violado!)"
        print("  [ok] reingerir abril substituiu SO abril, maio intacto (C8)")

        # 6. recorte de grupo elimina intragrupo (premortem C7)
        store_b = CanonicalStore.for_entidade(wd, "beta")
        store.ingest_competencia("itau-001", "2026-06", [
            normalizar({"data": "2026-06-01", "valor": 10000, "sinal": "D",
                        "descricao": "Transf p/ beta", "is_transferencia_intragrupo": True},
                       entidade_id="alfa", conta_id="itau-001", origem="ofx"),
            normalizar({"data": "2026-06-02", "valor": 3000, "sinal": "C", "descricao": "Receita real"},
                       entidade_id="alfa", conta_id="itau-001", origem="ofx"),
        ])
        store_b.ingest_competencia("bb-001", "2026-06", [
            normalizar({"data": "2026-06-01", "valor": 10000, "sinal": "C",
                        "descricao": "Recebido de alfa", "is_transferencia_intragrupo": True},
                       entidade_id="beta", conta_id="bb-001", origem="ofx"),
        ])
        grp = recorte_grupo({"alfa": store, "beta": store_b}, ["alfa", "beta"], "2026-06")
        # intragrupo (10k D + 10k C) sai; sobra so a receita real 3000
        assert grp["total_creditos"] == 3000 and grp["total_debitos"] == 0, \
            f"intragrupo nao foi eliminado: {grp}"
        print("  [ok] recorte_grupo eliminou transferencia intragrupo (C7)")

        store.close()
        store_b.close()

    print("RESULTADO: canonical.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(_auto_teste())
