#!/usr/bin/env python3
"""
bcb_client.py — Cliente da API SGS do Banco Central (urllib stdlib).

Le config/series-bcb.json (mapa modalidade -> codigo SGS). Busca AO VIVO a
serie na API publica do BCB (sem chave). Cache local em
scripts/data/cache-bcb/{codigo}.json com TTL.

TRAVA 4 / premortem C3 — NUNCA FABRICA TAXA:
  - API indisponivel + sem cache valido -> retorna status "indisponivel"
    com o texto fixo de config/compliance.json. JAMAIS estima/inventa numero.
  - Todo valor retornado carrega 'fonte', 'data_consulta' e 'origem'
    (api|cache) para rastreabilidade (auditoria-cfo R2).

Endpoint: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{N}?formato=json

Funcoes publicas:
  get_serie(codigo, n)        -> serie crua por codigo SGS
  get_taxa_modalidade(slug)   -> taxa media de credito por modalidade (config)
  get_macro(slug)             -> indicador macro (selic/cdi/ipca/igpm)

USO:
    python3 bcb_client.py serie 432 5
    python3 bcb_client.py modalidade capital_giro_pj_ate_365
    python3 bcb_client.py macro selic_meta
"""

from __future__ import annotations

import datetime as dt
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_FONTE = "Banco Central do Brasil — API SGS (https://api.bcb.gov.br)"
_TIMEOUT = 12  # segundos


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _config_series() -> dict[str, Any]:
    f = _plugin_root() / "config" / "series-bcb.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"series": {}, "cache_ttl_horas": 24}


def _compliance_indisponibilidade() -> str:
    f = _plugin_root() / "config" / "compliance.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data.get("indisponibilidade_fonte", "").replace("{fonte}", _FONTE)
    except (OSError, json.JSONDecodeError):
        return ("A fonte oficial (Banco Central — SGS) nao respondeu. NAO vou estimar "
                "o numero como fato (trava anti-halucinacao). Reexecute mais tarde.")


def _cache_dir() -> Path:
    d = _plugin_root() / "scripts" / "data" / "cache-bcb"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(codigo: int, n: int) -> Path:
    return _cache_dir() / f"sgs-{codigo}-ult{n}.json"


def _cache_valido(path: Path, ttl_horas: int) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        gravado = dt.datetime.fromisoformat(data.get("data_consulta", ""))
        idade = dt.datetime.now(dt.timezone.utc) - gravado
        if idade <= dt.timedelta(hours=ttl_horas):
            data["origem"] = "cache"
            return data
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return None


def _gravar_cache(path: Path, payload: dict) -> None:
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # cache e best-effort; nao quebra a consulta


def _indisponivel(codigo: int | None = None, modalidade: str | None = None) -> dict[str, Any]:
    """Retorno padrao quando a fonte oficial nao responde. NUNCA estima."""
    return {
        "status": "indisponivel",
        "codigo": codigo,
        "modalidade": modalidade,
        "fonte": _FONTE,
        "valor": None,            # explicitamente None — premortem C3
        "mensagem": _compliance_indisponibilidade(),
        "data_consulta": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Busca na API SGS
# ---------------------------------------------------------------------------

def get_serie(codigo: int, n: int = 12, *, usar_cache: bool = True) -> dict[str, Any]:
    """Busca os ultimos N pontos da serie SGS de codigo dado.

    Retorna {status: 'ok'|'indisponivel', valores: [...], ultimo: {...}, ...}.
    NUNCA fabrica: falha de rede + cache invalido => status 'indisponivel'.
    """
    cfg = _config_series()
    ttl = int(cfg.get("cache_ttl_horas", 24))
    cpath = _cache_path(codigo, n)

    if usar_cache:
        cached = _cache_valido(cpath, ttl)
        if cached:
            return cached

    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json"
    req = urllib.request.Request(url, headers={"User-Agent": "cfo-combativo-os/0.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (url fixa BCB)
            if resp.status != 200:
                return _stale_ou_indisponivel(cpath, codigo)
            dados = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"[bcb_client] SGS {codigo} indisponivel: {exc}", file=sys.stderr)
        return _stale_ou_indisponivel(cpath, codigo)

    if not isinstance(dados, list) or not dados:
        return _stale_ou_indisponivel(cpath, codigo)

    valores = []
    for ponto in dados:
        try:
            valores.append({"data": ponto.get("data", ""),
                            "valor": float(str(ponto.get("valor", "")).replace(",", "."))})
        except (TypeError, ValueError):
            continue

    payload = {
        "status": "ok",
        "codigo": codigo,
        "fonte": _FONTE,
        "origem": "api",
        "valores": valores,
        "ultimo": valores[-1] if valores else None,
        "data_consulta": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    _gravar_cache(cpath, payload)
    return payload


def _stale_ou_indisponivel(cpath: Path, codigo: int) -> dict[str, Any]:
    """API caiu: usa cache vencido (declarando como stale) ou indisponivel.

    Cache vencido ainda e DADO REAL ja buscado (nao fabricado) — pode ser
    usado se rotulado como 'stale'. Se nem cache vencido existe -> indisponivel.
    """
    if cpath.exists():
        try:
            data = json.loads(cpath.read_text(encoding="utf-8"))
            data["origem"] = "cache-stale"
            data["aviso"] = ("API do BCB nao respondeu; usando ultimo valor em cache "
                             f"(consultado em {data.get('data_consulta', '?')}). "
                             "Reexecute para atualizar.")
            return data
        except (OSError, json.JSONDecodeError):
            pass
    return _indisponivel(codigo=codigo)


def get_taxa_modalidade(slug: str) -> dict[str, Any]:
    """Taxa media de credito por modalidade (config/series-bcb.json -> series.credito)."""
    cfg = _config_series()
    credito = cfg.get("series", {}).get("credito", {})
    item = credito.get(slug)
    if not item:
        return {"status": "modalidade_desconhecida", "slug": slug, "valor": None,
                "modalidades_disponiveis": list(credito.keys())}
    res = get_serie(int(item["codigo"]), n=1)
    res["modalidade"] = slug
    res["unidade"] = item.get("unidade")
    res["descricao"] = item.get("descricao")
    res["perfil"] = item.get("perfil")
    return res


def get_macro(slug: str) -> dict[str, Any]:
    """Indicador macro (selic_meta/cdi_diario/ipca_mensal/igpm_mensal)."""
    cfg = _config_series()
    macro = cfg.get("series", {}).get("macro", {})
    item = macro.get(slug)
    if not item:
        return {"status": "indicador_desconhecido", "slug": slug, "valor": None,
                "indicadores_disponiveis": list(macro.keys())}
    n = 12 if slug in ("ipca_mensal", "igpm_mensal") else 1
    res = get_serie(int(item["codigo"]), n=n)
    res["indicador"] = slug
    res["unidade"] = item.get("unidade")
    res["descricao"] = item.get("descricao")
    return res


# ---------------------------------------------------------------------------
# Auto-teste (SEM rede — valida cache, indisponibilidade e NAO-fabricacao)
# ---------------------------------------------------------------------------

def _auto_teste() -> int:
    print("== AUTO-TESTE bcb_client.py (sem rede — anti-halucinacao C3) ==")
    falhas = 0

    # 1. config carrega e tem as series do spec
    cfg = _config_series()
    credito = cfg.get("series", {}).get("credito", {})
    assert "capital_giro_pj_ate_365" in credito, "config series-bcb.json sem modalidade esperada"
    assert credito["capital_giro_pj_ate_365"]["codigo"] == 20722, "codigo SGS divergente do spec"
    print("  [ok] config/series-bcb.json carregado com codigos do spec")

    # 2. modalidade desconhecida nao fabrica
    r = get_taxa_modalidade("modalidade_que_nao_existe")
    assert r["status"] == "modalidade_desconhecida" and r["valor"] is None, "deveria recusar slug desconhecido"
    print("  [ok] modalidade desconhecida -> valor None, nao fabrica")

    # 3. indicador macro desconhecido nao fabrica
    r2 = get_macro("indicador_invalido")
    assert r2["status"] == "indicador_desconhecido" and r2["valor"] is None
    print("  [ok] macro desconhecido -> valor None, nao fabrica")

    # 4. retorno de indisponibilidade carrega o texto de compliance e valor None (C3)
    ind = _indisponivel(codigo=432)
    assert ind["status"] == "indisponivel" and ind["valor"] is None, "indisponivel deve ter valor None"
    assert "trava" in ind["mensagem"].lower() or "estimar" in ind["mensagem"].lower(), \
        "mensagem de indisponibilidade nao veio do compliance"
    print("  [ok] indisponibilidade declara fonte e valor None (NUNCA fabrica — C3)")

    # 5. cache: grava e le com origem rastreavel
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        cpath = Path(td) / "sgs-999-ult1.json"
        _gravar_cache(cpath, {
            "status": "ok", "codigo": 999, "fonte": _FONTE, "origem": "api",
            "valores": [{"data": "01/04/2026", "valor": 1.23}],
            "ultimo": {"data": "01/04/2026", "valor": 1.23},
            "data_consulta": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        v = _cache_valido(cpath, ttl_horas=24)
        assert v and v["origem"] == "cache" and v["ultimo"]["valor"] == 1.23, "cache valido nao recuperou"
        print("  [ok] cache TTL valido recuperado com origem='cache'")

        # 6. cache vencido vira 'cache-stale' (dado real, nao fabricado), nunca some
        velho = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=48)).isoformat()
        _gravar_cache(cpath, {"status": "ok", "codigo": 999, "valores": [],
                              "data_consulta": velho})
        assert _cache_valido(cpath, ttl_horas=24) is None, "cache vencido nao deveria contar como valido"
        stale = _stale_ou_indisponivel(cpath, 999)
        assert stale["origem"] == "cache-stale", "cache vencido deveria virar stale, nao sumir"
        print("  [ok] cache vencido -> 'cache-stale' rotulado (dado real, nao fabricado)")

    print("RESULTADO: bcb_client.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


def _main() -> int:
    if len(sys.argv) < 2:
        print("USO: python3 bcb_client.py [serie <codigo> [n] | modalidade <slug> | macro <slug>]",
              file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "serie" and len(sys.argv) >= 3:
        res = get_serie(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    elif cmd == "modalidade" and len(sys.argv) >= 3:
        res = get_taxa_modalidade(sys.argv[2])
    elif cmd == "macro" and len(sys.argv) >= 3:
        res = get_macro(sys.argv[2])
    else:
        print("Comando invalido.", file=sys.stderr)
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(_main())
