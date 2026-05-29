#!/usr/bin/env python3
"""
csv_parser.py — Parser de extratos CSV multi-banco -> schema canonico (§3).

Auto-deteccao de layout por banco (Itau/BB/Bradesco/Santander/Nubank/Inter/
C6/Caixa) + mapeamento de colunas SALVAVEL por banco para reuso.

Estrategia (premortem C2 — degradacao graciosa):
  - Stdlib `csv` + heuristica de cabecalho/separador/decimal (SEM pandas).
  - pandas e OPCIONAL (so acelera arquivos grandes); nunca importado no topo.

Mapeamentos salvos em: scripts/data/csv-layouts/{banco}.json — assim o
operador mapeia uma vez por banco e reusa nas proximas ingestoes.

USO:
    python3 csv_parser.py <arquivo.csv> [entidade_id] [conta_id] [banco]
"""

from __future__ import annotations

import csv as _csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Sinonimos de coluna por papel canonico (heuristica de auto-mapeamento)
_SINONIMOS = {
    "data": ["data", "data lancamento", "data lanc", "date", "dt", "data mov",
             "data movimento", "data da transacao", "data transacao"],
    "valor": ["valor", "valor (r$)", "amount", "montante", "vlr", "value",
              "valor lancamento", "valor da transacao"],
    "descricao": ["descricao", "historico", "lancamento", "memo", "description",
                  "detalhe", "transacao", "estabelecimento", "titulo"],
    "credito": ["credito", "entrada", "credit", "creditos", "c"],
    "debito": ["debito", "saida", "debit", "debitos", "d"],
    "tipo": ["tipo", "tipo lancamento", "credito/debito", "c/d", "natureza"],
    "contraparte": ["favorecido", "beneficiario", "pagador", "contraparte",
                    "destino", "origem", "nome"],
}

# Assinaturas de cabecalho conhecidas (auto-deteccao de banco)
_ASSINATURAS_BANCO = {
    "nubank": ["data", "valor", "identificador", "descricao"],
    "inter": ["data lançamento", "histórico", "valor", "saldo"],
    "itau": ["data", "lançamento", "ag./origem", "valor"],
    "bb": ["data", "histórico", "valor", "saldo"],
    "bradesco": ["data", "histórico", "crédito", "débito"],
    "santander": ["data", "histórico", "valor", "saldo"],
    "c6": ["data", "descrição", "valor", "categoria"],
    "caixa": ["data mov.", "histórico", "valor", "saldo"],
}


def _layout_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "data" / "csv-layouts"
    return d


def _norm(s: str) -> str:
    s = s.strip().lower()
    for a, b in (("á", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"),
                 ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"), ("ú", "u"), ("ç", "c")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def _ler_texto(path: str) -> str:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _detectar_separador(linhas: list[str]) -> str:
    """Detecta o separador olhando as primeiras linhas (nao so a 1a — que pode
    ser um titulo sem separador). Escolhe o separador mais frequente e consistente.
    """
    if isinstance(linhas, str):
        linhas = [linhas]
    melhor, score = ",", -1
    for sep in (";", ",", "\t", "|"):
        contagens = [ln.count(sep) for ln in linhas[:10] if ln.strip()]
        # consistencia: linhas de dados costumam ter a mesma contagem > 0
        positivas = [c for c in contagens if c > 0]
        if positivas:
            s = sum(positivas)
            if s > score:
                melhor, score = sep, s
    return melhor


def _achar_cabecalho(linhas: list[list[str]]) -> int:
    """Acha a linha de cabecalho (a 1a que casa com >=2 papeis conhecidos)."""
    todos = {syn for syns in _SINONIMOS.values() for syn in syns}
    for i, row in enumerate(linhas[:15]):
        cols = [_norm(c) for c in row]
        if sum(1 for c in cols if c in todos) >= 2:
            return i
    return 0


def _detectar_banco(header: list[str], banco_hint: str | None) -> str | None:
    if banco_hint:
        return _norm(banco_hint)
    h = {_norm(c) for c in header}
    melhor, score = None, 0
    for banco, assinatura in _ASSINATURAS_BANCO.items():
        s = sum(1 for a in assinatura if _norm(a) in h)
        if s > score:
            melhor, score = banco, s
    return melhor if score >= 2 else None


def _mapear_colunas(header: list[str]) -> dict[str, int]:
    """Mapeia papel canonico -> indice da coluna por sinonimos."""
    mapa: dict[str, int] = {}
    cols = [_norm(c) for c in header]
    for papel, syns in _SINONIMOS.items():
        for i, c in enumerate(cols):
            if c in syns or any(c == _norm(s) for s in syns):
                mapa[papel] = i
                break
    return mapa


def _carregar_layout_salvo(banco: str | None) -> dict | None:
    if not banco:
        return None
    f = _layout_dir() / f"{_norm(banco)}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def salvar_layout(banco: str, mapa: dict, *, separador: str, header_idx: int,
                  decimal: str = ",") -> Path:
    """Persiste o mapeamento de colunas de um banco para reuso futuro."""
    d = _layout_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{_norm(banco)}.json"
    f.write_text(json.dumps({
        "banco": _norm(banco), "mapa": mapa, "separador": separador,
        "header_idx": header_idx, "decimal": decimal,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


def _detectar_decimal(amostra: list[str]) -> str:
    """Decide se o decimal e ',' (BR) ou '.' (US) olhando uma amostra de valores.

    Heuristica: se a virgula aparece como ultimo separador (xxx,dd) e mais comum
    que ponto nessa posicao, decimal e ','. Caso contrario, '.'.
    """
    br = us = 0
    for s in amostra:
        s = str(s).strip()
        if re.search(r",\d{1,2}$", s):   # termina em ,dd -> decimal virgula
            br += 1
        elif re.search(r"\.\d{1,2}$", s):  # termina em .dd -> decimal ponto
            us += 1
    return "." if us > br else ","


def _br_to_float(s: str, decimal: str = ",") -> float:
    s = str(s).strip().replace("R$", "").replace(" ", "")
    neg = s.startswith("-") or s.startswith("(")
    s = s.lstrip("-").strip("()")
    if decimal == ",":
        # milhar='.', decimal=','  -> remove pontos, troca virgula por ponto
        s = s.replace(".", "").replace(",", ".")
    else:
        # milhar=',', decimal='.'  -> remove virgulas (de milhar), mantem ponto
        s = s.replace(",", "")
    try:
        v = float(s) if s else 0.0
    except ValueError:
        v = 0.0
    return -v if neg else v


def parse_csv(path: str, *, entidade_id: str | None = None,
              conta_id: str | None = None, banco: str | None = None,
              salvar: bool = False) -> dict[str, Any]:
    """Le CSV de extrato e retorna transacoes no schema canonico (§3)."""
    if not Path(path).exists():
        return {"ok": False, "erro": "arquivo_nao_encontrado", "caminho": path, "transacoes": []}

    try:
        texto = _ler_texto(path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "erro": f"leitura_falhou: {exc}", "transacoes": []}

    linhas_brutas = [ln for ln in texto.splitlines() if ln.strip()]
    if not linhas_brutas:
        return {"ok": False, "erro": "csv_vazio", "transacoes": []}

    layout_salvo = _carregar_layout_salvo(banco)
    sep = layout_salvo["separador"] if layout_salvo else _detectar_separador(linhas_brutas)
    decimal = layout_salvo.get("decimal", ",") if layout_salvo else ","

    parsed = list(_csv.reader(linhas_brutas, delimiter=sep))
    header_idx = layout_salvo["header_idx"] if layout_salvo else _achar_cabecalho(parsed)
    header = parsed[header_idx]
    banco_det = _detectar_banco(header, banco)
    mapa = layout_salvo["mapa"] if layout_salvo else _mapear_colunas(header)

    if "data" not in mapa or ("valor" not in mapa and not ("credito" in mapa or "debito" in mapa)):
        return {
            "ok": False,
            "erro": "layout_nao_reconhecido",
            "mensagem": ("Nao identifiquei as colunas de data e valor. "
                         "Informe o mapeamento manualmente para eu salvar este layout (PA-14: nao suponho)."),
            "header_detectado": header,
            "banco_detectado": banco_det,
            "transacoes": [],
        }

    # Auto-deteccao do separador decimal a partir de uma amostra das colunas de valor
    # (so se nao veio de layout salvo). Evita confundir milhar '.' com decimal.
    if not layout_salvo:
        idxs = [mapa[k] for k in ("valor", "credito", "debito") if k in mapa]
        amostra: list[str] = []
        for row in parsed[header_idx + 1: header_idx + 40]:
            for ix in idxs:
                if ix < len(row) and row[ix].strip():
                    amostra.append(row[ix])
        if amostra:
            decimal = _detectar_decimal(amostra)

    crus: list[dict] = []
    for row in parsed[header_idx + 1:]:
        if len(row) <= mapa["data"]:
            continue
        data = row[mapa["data"]].strip()
        if not re.search(r"\d{2}[/-]\d{2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}", data):
            continue  # linha-lixo / rodape de saldo

        if "valor" in mapa and mapa["valor"] < len(row):
            valor = _br_to_float(row[mapa["valor"]], decimal)
            sinal = "D" if valor < 0 else "C"
        else:
            cred = _br_to_float(row[mapa["credito"]], decimal) if "credito" in mapa and mapa["credito"] < len(row) else 0.0
            deb = _br_to_float(row[mapa["debito"]], decimal) if "debito" in mapa and mapa["debito"] < len(row) else 0.0
            valor = cred if cred else -deb
            sinal = "C" if cred else "D"

        if valor == 0:
            continue
        desc = row[mapa["descricao"]].strip() if "descricao" in mapa and mapa["descricao"] < len(row) else ""
        contra = row[mapa["contraparte"]].strip() if "contraparte" in mapa and mapa["contraparte"] < len(row) else None
        crus.append({
            "data": data, "valor": abs(valor), "sinal": sinal,
            "descricao": desc, "contraparte": contra, "banco": banco_det,
        })

    if salvar and banco_det:
        salvar_layout(banco_det, mapa, separador=sep, header_idx=header_idx, decimal=decimal)

    if entidade_id and conta_id:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
            from canonical import normalizar  # type: ignore
            txs = [normalizar(c, entidade_id=entidade_id, conta_id=conta_id,
                              origem="csv", banco=c.get("banco")).to_dict() for c in crus]
            return {"ok": True, "banco_detectado": banco_det, "qtd": len(txs), "transacoes": txs}
        except Exception as exc:  # noqa: BLE001
            print(f"[csv_parser] normalizacao falhou ({exc}); retornando crus", file=sys.stderr)

    return {"ok": True, "banco_detectado": banco_det, "qtd": len(crus),
            "transacoes": crus, "aviso": "informe entidade_id e conta_id para normalizar"}


# ---------------------------------------------------------------------------
# Auto-teste (CSV SINTETICO — 2 layouts: valor unico e credito/debito)
# ---------------------------------------------------------------------------

_CSV_NUBANK = """Data,Valor,Identificador,Descrição
05/04/2026,5000.00,abc-1,Transferência recebida
12/04/2026,-1200.50,abc-2,Pagamento Aluguel
SALDO,,,
"""

_CSV_BRADESCO = """Extrato Conta Corrente
Data;Histórico;Crédito;Débito
05/04/2026;DEPOSITO;3.000,00;
12/04/2026;TARIFA PACOTE;;45,90
"""


def _auto_teste() -> int:
    import tempfile
    print("== AUTO-TESTE csv_parser.py (CSV sintetico) ==")
    falhas = 0
    with tempfile.TemporaryDirectory() as td:
        # 1. layout valor unico (Nubank), separador virgula, decimal ponto
        f1 = Path(td) / "nubank.csv"
        f1.write_text(_CSV_NUBANK, encoding="utf-8")
        r1 = parse_csv(str(f1), entidade_id="joao", conta_id="nubank-001")
        assert r1["ok"] and r1["qtd"] == 2, f"nubank falhou: {r1}"
        assert r1["transacoes"][0]["sinal"] == "C" and r1["transacoes"][1]["sinal"] == "D"
        assert r1["transacoes"][1]["valor"] == 1200.50, "valor negativo mal lido"
        print("  [ok] layout valor-unico (linha SALDO ignorada como lixo)")

        # 2. layout credito/debito separados (Bradesco), separador ;, decimal virgula
        f2 = Path(td) / "bradesco.csv"
        f2.write_text(_CSV_BRADESCO, encoding="utf-8")
        r2 = parse_csv(str(f2), entidade_id="alfa", conta_id="brad-001")
        assert r2["ok"] and r2["qtd"] == 2, f"bradesco falhou: {r2}"
        assert r2["transacoes"][0]["valor"] == 3000.0 and r2["transacoes"][0]["sinal"] == "C"
        assert r2["transacoes"][1]["valor"] == 45.90 and r2["transacoes"][1]["sinal"] == "D"
        assert r2["banco_detectado"] == "bradesco", f"banco mal detectado: {r2['banco_detectado']}"
        print("  [ok] layout credito/debito + cabecalho deslocado + deteccao de banco")

        # 3. layout irreconhecivel pede mapeamento (PA-14) sem quebrar
        f3 = Path(td) / "ruim.csv"
        f3.write_text("col_x;col_y\n1;2\n", encoding="utf-8")
        r3 = parse_csv(str(f3))
        assert not r3["ok"] and r3["erro"] == "layout_nao_reconhecido", f"deveria pedir mapeamento: {r3}"
        print("  [ok] layout desconhecido -> pede mapeamento, nao supoe (PA-14)")

    print("RESULTADO: csv_parser.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


def _main() -> int:
    if len(sys.argv) < 2:
        print("USO: python3 csv_parser.py <arquivo.csv> [entidade_id] [conta_id] [banco]", file=sys.stderr)
        return 2
    res = parse_csv(sys.argv[1],
                    entidade_id=sys.argv[2] if len(sys.argv) > 2 else None,
                    conta_id=sys.argv[3] if len(sys.argv) > 3 else None,
                    banco=sys.argv[4] if len(sys.argv) > 4 else None)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(_main())
