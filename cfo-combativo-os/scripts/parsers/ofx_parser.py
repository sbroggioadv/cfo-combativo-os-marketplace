#!/usr/bin/env python3
"""
ofx_parser.py — Parser de extratos OFX/QFX -> schema canonico (design-spec §3).

Estrategia (premortem C2 — degradacao graciosa, NUNCA quebra a sessao):
  1. ofxparse (pip install ofxparse) — robusto, OFX 1.x SGML + 2.x XML
  2. fallback interno: xml.etree para OFX 2.x (XML) + parser SGML minimo
     por regex para OFX 1.x (stdlib only)
  3. se nada funcionar: retorna erro ESTRUTURADO instruindo pip install

REGRA DURA: nenhum import de ofxparse no topo do modulo — so DENTRO da funcao.
Se a lib faltar, o modulo ainda importa e o fallback stdlib roda. Isso evita
o crash do Cowork (licao hook-utils 2026-05-26).

USO:
    python3 ofx_parser.py <arquivo.ofx> [entidade_id] [conta_id]

Retorna lista de dicts no schema canonico (via normalizar de canonical.py
quando entidade/conta sao informados; senao dicts crus prontos pra normalizar).
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _erro_dependencia() -> dict[str, Any]:
    return {
        "ok": False,
        "erro": "dependencia_e_fallback_indisponiveis",
        "mensagem": (
            "Nao consegui ler o OFX nem com ofxparse nem com o parser interno. "
            "Para o caminho robusto: pip install ofxparse"
        ),
        "transacoes": [],
    }


def _data_ofx(raw: str) -> str:
    """Converte DTPOSTED OFX (YYYYMMDD[HHMMSS][.fff][TZ]) -> YYYY-MM-DD."""
    if not raw:
        return ""
    m = re.match(r"(\d{4})(\d{2})(\d{2})", raw.strip())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


# ---------------------------------------------------------------------------
# Estrategia 1 — ofxparse
# ---------------------------------------------------------------------------

def _parse_ofxparse(path: str) -> list[dict] | None:
    try:
        from ofxparse import OfxParser  # type: ignore  (import DENTRO da funcao)
    except ImportError:
        return None
    try:
        with open(path, "rb") as fh:
            ofx = OfxParser.parse(fh)
        saida: list[dict] = []
        for acc in getattr(ofx, "accounts", []) or []:
            banco = (getattr(acc.institution, "organization", None)
                     if getattr(acc, "institution", None) else None)
            stmt = getattr(acc, "statement", None)
            if not stmt:
                continue
            for tx in getattr(stmt, "transactions", []) or []:
                valor = float(tx.amount)
                saida.append({
                    "data": tx.date.strftime("%Y-%m-%d") if getattr(tx, "date", None) else "",
                    "valor": abs(valor),
                    "sinal": "D" if valor < 0 else "C",
                    "descricao": (getattr(tx, "memo", "") or getattr(tx, "payee", "") or "").strip(),
                    "contraparte": getattr(tx, "payee", None) or None,
                    "doc_vinculado": getattr(tx, "id", None) or None,
                    "banco": banco,
                })
        return saida
    except Exception as exc:  # noqa: BLE001
        print(f"[ofx_parser] ofxparse falhou: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Estrategia 2 — fallback stdlib (XML 2.x + SGML 1.x por regex)
# ---------------------------------------------------------------------------

def _ler_texto(path: str) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_fallback(path: str) -> list[dict] | None:
    """Parser interno por regex — funciona para OFX 1.x (SGML) e 2.x (XML).

    OFX e quase sempre tags <KEY>valor (SGML sem fechamento) — regex pega ambos.
    """
    try:
        texto = _ler_texto(path)
    except Exception as exc:  # noqa: BLE001
        print(f"[ofx_parser] leitura do arquivo falhou: {exc}", file=sys.stderr)
        return None

    if "<OFX>" not in texto.upper() and "STMTTRN" not in texto.upper():
        return None  # nao parece OFX

    banco_m = re.search(r"<ORG>\s*([^\n<]+)", texto, re.IGNORECASE)
    banco = banco_m.group(1).strip() if banco_m else None

    saida: list[dict] = []
    # cada transacao vive em <STMTTRN> ... </STMTTRN> (XML) ou ate o proximo STMTTRN (SGML)
    blocos = re.split(r"<STMTTRN>", texto, flags=re.IGNORECASE)[1:]
    for bloco in blocos:
        def _tag(tag: str) -> str:
            m = re.search(rf"<{tag}>\s*([^\n<]+)", bloco, re.IGNORECASE)
            return m.group(1).strip() if m else ""

        amt_raw = _tag("TRNAMT").replace(",", ".")
        try:
            valor = float(amt_raw)
        except ValueError:
            continue
        memo = _tag("MEMO") or _tag("NAME")
        saida.append({
            "data": _data_ofx(_tag("DTPOSTED")),
            "valor": abs(valor),
            "sinal": "D" if valor < 0 else "C",
            "descricao": memo,
            "contraparte": _tag("NAME") or None,
            "doc_vinculado": _tag("FITID") or None,
            "banco": banco,
        })
    return saida if saida else None


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def parse_ofx(path: str, *, entidade_id: str | None = None,
              conta_id: str | None = None) -> dict[str, Any]:
    """Le OFX/QFX e retorna dict com transacoes no schema canonico.

    Se entidade_id e conta_id forem dados, normaliza via canonical.py
    (transacoes canonicas completas). Senao, devolve dicts crus.
    """
    if not Path(path).exists():
        return {"ok": False, "erro": "arquivo_nao_encontrado", "caminho": path, "transacoes": []}

    crus: list[dict] | None = _parse_ofxparse(path)
    metodo = "ofxparse"
    if crus is None:
        crus = _parse_fallback(path)
        metodo = "fallback-stdlib"
    if crus is None:
        return _erro_dependencia()

    if entidade_id and conta_id:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
            from canonical import normalizar  # type: ignore
            txs = [normalizar(c, entidade_id=entidade_id, conta_id=conta_id,
                              origem="ofx", banco=c.get("banco")).to_dict()
                   for c in crus]
            return {"ok": True, "metodo": metodo, "qtd": len(txs), "transacoes": txs}
        except Exception as exc:  # noqa: BLE001 — degrada para crus
            print(f"[ofx_parser] normalizacao canonica falhou ({exc}); retornando crus", file=sys.stderr)

    return {"ok": True, "metodo": metodo, "qtd": len(crus), "transacoes": crus,
            "aviso": "informe entidade_id e conta_id para normalizar ao schema canonico"}


# ---------------------------------------------------------------------------
# Auto-teste (OFX SINTETICO — testa fallback stdlib SEM ofxparse)
# ---------------------------------------------------------------------------

_OFX_SINTETICO = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKACCTFROM><ORG>BANCO SINTETICO<ACCTID>00012345</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260405120000<TRNAMT>5000.00<FITID>TX001<MEMO>RECEITA SERVICO A</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260412<TRNAMT>-1200.50<FITID>TX002<NAME>IMOBILIARIA Z<MEMO>ALUGUEL ABRIL</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""


def _auto_teste() -> int:
    import tempfile
    print("== AUTO-TESTE ofx_parser.py (OFX sintetico, sem ofxparse) ==")
    falhas = 0
    with tempfile.TemporaryDirectory() as td:
        ofx = Path(td) / "extrato.ofx"
        ofx.write_text(_OFX_SINTETICO, encoding="utf-8")

        # forca o caminho de fallback testando-o diretamente
        crus = _parse_fallback(str(ofx))
        assert crus and len(crus) == 2, f"fallback deveria achar 2 transacoes: {crus}"
        assert crus[0]["data"] == "2026-04-05" and crus[0]["sinal"] == "C", "credito mal lido"
        assert crus[1]["sinal"] == "D" and crus[1]["valor"] == 1200.50, "debito mal lido"
        print("  [ok] fallback stdlib leu OFX SGML sintetico (2 tx, C+D)")

        # API publica normaliza ao canonico
        res = parse_ofx(str(ofx), entidade_id="alfa", conta_id="itau-cc-001")
        assert res["ok"] and res["qtd"] == 2, f"parse_ofx falhou: {res}"
        assert res["transacoes"][0]["competencia"] == "2026-04", "competencia nao derivou"
        assert res["transacoes"][0]["id"], "hash canonico nao gerado"
        print("  [ok] parse_ofx normalizou ao schema canonico")

        # arquivo inexistente degrada sem excecao
        res_err = parse_ofx(str(Path(td) / "nao-existe.ofx"))
        assert not res_err["ok"] and res_err["erro"] == "arquivo_nao_encontrado", "deveria degradar"
        print("  [ok] arquivo inexistente -> erro estruturado, sem crash")

    print("RESULTADO: ofx_parser.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


def _main() -> int:
    if len(sys.argv) < 2:
        print("USO: python3 ofx_parser.py <arquivo.ofx> [entidade_id] [conta_id]", file=sys.stderr)
        return 2
    res = parse_ofx(sys.argv[1],
                    entidade_id=sys.argv[2] if len(sys.argv) > 2 else None,
                    conta_id=sys.argv[3] if len(sys.argv) > 3 else None)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(_main())
