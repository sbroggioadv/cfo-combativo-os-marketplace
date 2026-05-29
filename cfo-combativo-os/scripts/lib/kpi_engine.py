#!/usr/bin/env python3
"""
kpi_engine.py — Motor de calculo dos KPIs de CFO.

Le as formulas e faixas semaforicas de config/indicadores.json e calcula
cada indicador a partir de um dict de insumos contabeis (AC, PC, Estoque,
Receita, EBITDA, etc).

Cada KPI retornado carrega (premortem C3 — nada sem origem):
  - valor (None se faltar insumo — NUNCA inventa)
  - classificacao semaforica (verde/amarelo/vermelho/indefinido)
  - base_calculo: dict com os insumos usados (rastreabilidade p/ auditoria-cfo R2)
  - formula: string textual da formula aplicada

REGRA: insumo ausente => valor None + status 'insumo_faltante'. Jamais
assume zero ou estima. Divisao por zero => 'indefinido'.

USO:
    python3 kpi_engine.py   (roda auto-teste com insumos sinteticos)
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _carregar_indicadores() -> dict[str, Any]:
    f = _plugin_root() / "config" / "indicadores.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# Definicao de cada KPI: insumos exigidos + funcao de calculo.
# As funcoes recebem o dict de insumos e devolvem float ou None (div/0).
def _safe_div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b not in (0, 0.0, None) else None


_CALC: dict[str, tuple[list[str], Callable[[dict], float | None]]] = {
    # Liquidez
    "liquidez_corrente": (["AC", "PC"], lambda d: _safe_div(d["AC"], d["PC"])),
    "liquidez_seca": (["AC", "Estoque", "PC"], lambda d: _safe_div(d["AC"] - d["Estoque"], d["PC"])),
    "liquidez_imediata": (["Disponivel", "PC"], lambda d: _safe_div(d["Disponivel"], d["PC"])),
    # Endividamento
    "endividamento_geral": (["PassivoTotal", "AtivoTotal"], lambda d: _safe_div(d["PassivoTotal"], d["AtivoTotal"])),
    "divida_liquida_ebitda": (["DividaLiquida", "EBITDA"], lambda d: _safe_div(d["DividaLiquida"], d["EBITDA"])),
    "alavancagem": (["PassivoTotal", "PL"], lambda d: _safe_div(d["PassivoTotal"], d["PL"])),
    "cobertura_juros_icsd": (["EBIT", "DespesaFinanceira"], lambda d: _safe_div(d["EBIT"], d["DespesaFinanceira"])),
    # Prazos/ciclo
    "pmr": (["ContasReceber", "ReceitaBruta", "dias_periodo"],
            lambda d: round(_safe_div(d["ContasReceber"], d["ReceitaBruta"]) * d["dias_periodo"], 1)
            if _safe_div(d["ContasReceber"], d["ReceitaBruta"]) is not None else None),
    "pmp": (["ContasPagar", "Compras", "dias_periodo"],
            lambda d: round(_safe_div(d["ContasPagar"], d["Compras"]) * d["dias_periodo"], 1)
            if _safe_div(d["ContasPagar"], d["Compras"]) is not None else None),
    "pme": (["Estoque", "CMV", "dias_periodo"],
            lambda d: round(_safe_div(d["Estoque"], d["CMV"]) * d["dias_periodo"], 1)
            if _safe_div(d["Estoque"], d["CMV"]) is not None else None),
    # Rentabilidade (% como fracao)
    "margem_bruta": (["Receita", "CMV"], lambda d: _safe_div(d["Receita"] - d["CMV"], d["Receita"])),
    "margem_ebitda": (["EBITDA", "Receita"], lambda d: _safe_div(d["EBITDA"], d["Receita"])),
    "margem_liquida": (["LucroLiquido", "Receita"], lambda d: _safe_div(d["LucroLiquido"], d["Receita"])),
    "roe": (["LucroLiquido", "PL"], lambda d: _safe_div(d["LucroLiquido"], d["PL"])),
    "roa": (["LucroLiquido", "AtivoTotal"], lambda d: _safe_div(d["LucroLiquido"], d["AtivoTotal"])),
    # Operacional
    "ponto_equilibrio": (["CustosFixos", "CustosVariaveis", "Receita"],
                         lambda d: round(d["CustosFixos"] / (1 - (d["CustosVariaveis"] / d["Receita"])), 2)
                         if d["Receita"] and (1 - (d["CustosVariaveis"] / d["Receita"])) != 0 else None),
    "giro_ativos": (["Receita", "AtivoTotal"], lambda d: _safe_div(d["Receita"], d["AtivoTotal"])),
    "giro_estoque": (["CMV", "EstoqueMedio"], lambda d: _safe_div(d["CMV"], d["EstoqueMedio"])),
    "ticket_medio": (["Receita", "NumeroVendas"], lambda d: _safe_div(d["Receita"], d["NumeroVendas"])),
    "ncg": (["ContasReceber", "Estoque", "ContasPagar"],
            lambda d: round((d["ContasReceber"] + d["Estoque"]) - d["ContasPagar"], 2)),
}

# Ciclo financeiro depende de outros KPIs (PMR + PME - PMP)
_DERIVADOS = {
    "ciclo_financeiro": ["pmr", "pme", "pmp"],
}


def _faixa_para_classificacao(valor: float, faixas: dict[str, str]) -> str:
    """Avalia faixas tipo '>=1.5', '1.0-1.49', '<1.0' -> verde/amarelo/vermelho."""
    for cor in ("verde", "amarelo", "vermelho"):
        expr = faixas.get(cor)
        if not expr:
            continue
        if _avaliar_faixa(valor, expr):
            return cor
    return "indefinido"


def _avaliar_faixa(valor: float, expr: str) -> bool:
    expr = expr.strip()
    m_range = re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", expr)
    if m_range:
        lo, hi = float(m_range.group(1)), float(m_range.group(2))
        return lo <= valor <= hi
    m_op = re.match(r"^(>=|<=|>|<)\s*([\d.]+)$", expr)
    if m_op:
        op, ref = m_op.group(1), float(m_op.group(2))
        return {">=": valor >= ref, "<=": valor <= ref,
                ">": valor > ref, "<": valor < ref}[op]
    return False


def _achar_def_no_config(cfg: dict, nome: str) -> dict | None:
    for grupo in cfg.values():
        if isinstance(grupo, dict) and nome in grupo and isinstance(grupo[nome], dict):
            return grupo[nome]
    return None


def calcular_kpi(nome: str, insumos: dict[str, Any], cfg: dict | None = None) -> dict[str, Any]:
    """Calcula UM KPI. Retorna valor + classificacao + base rastreavel."""
    cfg = cfg if cfg is not None else _carregar_indicadores()
    definicao = _achar_def_no_config(cfg, nome) or {}

    # KPI derivado (ex.: ciclo_financeiro)
    if nome in _DERIVADOS:
        partes = {p: calcular_kpi(p, insumos, cfg) for p in _DERIVADOS[nome]}
        if any(partes[p]["valor"] is None for p in partes):
            return {"kpi": nome, "valor": None, "status": "insumo_faltante",
                    "classificacao": "indefinido", "base_calculo": partes,
                    "formula": definicao.get("formula", "PMR + PME - PMP")}
        valor = round(partes["pmr"]["valor"] + partes["pme"]["valor"] - partes["pmp"]["valor"], 1)
        return {"kpi": nome, "valor": valor, "status": "ok", "classificacao": "indefinido",
                "base_calculo": {p: partes[p]["valor"] for p in partes},
                "formula": definicao.get("formula", "PMR + PME - PMP"),
                "interpretacao": definicao.get("interpretacao")}

    if nome not in _CALC:
        return {"kpi": nome, "valor": None, "status": "kpi_desconhecido",
                "classificacao": "indefinido", "base_calculo": {}}

    exigidos, fn = _CALC[nome]
    faltantes = [k for k in exigidos if k not in insumos or insumos[k] is None]
    if faltantes:
        # premortem C3: NAO inventa, declara o que faltou
        return {"kpi": nome, "valor": None, "status": "insumo_faltante",
                "classificacao": "indefinido", "insumos_faltantes": faltantes,
                "base_calculo": {k: insumos.get(k) for k in exigidos},
                "formula": definicao.get("formula", "")}

    try:
        valor = fn(insumos)
    except (ZeroDivisionError, TypeError):
        valor = None

    if valor is None:
        return {"kpi": nome, "valor": None, "status": "indefinido_divisao_zero",
                "classificacao": "indefinido",
                "base_calculo": {k: insumos.get(k) for k in exigidos},
                "formula": definicao.get("formula", "")}

    faixas = definicao.get("faixas")
    classificacao = _faixa_para_classificacao(valor, faixas) if faixas else "sem_faixa"

    return {
        "kpi": nome,
        "valor": valor,
        "status": "ok",
        "classificacao": classificacao,
        "unidade": definicao.get("unidade"),
        "base_calculo": {k: insumos.get(k) for k in exigidos},
        "formula": definicao.get("formula", ""),
    }


def calcular_painel(insumos: dict[str, Any], cfg: dict | None = None) -> dict[str, Any]:
    """Calcula TODOS os KPIs possiveis com os insumos disponiveis."""
    cfg = cfg if cfg is not None else _carregar_indicadores()
    resultado: dict[str, Any] = {}
    for nome in list(_CALC.keys()) + list(_DERIVADOS.keys()):
        resultado[nome] = calcular_kpi(nome, insumos, cfg)
    calculados = sum(1 for r in resultado.values() if r["valor"] is not None)
    return {"kpis": resultado, "total": len(resultado), "calculados": calculados,
            "nao_calculados_por_falta_de_insumo": len(resultado) - calculados}


# ---------------------------------------------------------------------------
# Auto-teste (insumos SINTETICOS)
# ---------------------------------------------------------------------------

def _auto_teste() -> int:
    print("== AUTO-TESTE kpi_engine.py (insumos sinteticos) ==")
    falhas = 0

    insumos = {
        "AC": 168000, "PC": 100000, "Estoque": 40000, "Disponivel": 50000,
        "PassivoTotal": 210000, "AtivoTotal": 500000, "PL": 290000,
        "DividaLiquida": 210000, "EBITDA": 100000, "EBIT": 90000, "DespesaFinanceira": 30000,
        "ContasReceber": 80000, "ReceitaBruta": 600000, "dias_periodo": 30,
        "ContasPagar": 50000, "Compras": 300000, "CMV": 360000,
        "Receita": 600000, "LucroLiquido": 60000,
        "CustosFixos": 80000, "CustosVariaveis": 360000,
        "EstoqueMedio": 40000, "NumeroVendas": 1200,
    }

    # 1. liquidez corrente = 1.68 -> verde
    r = calcular_kpi("liquidez_corrente", insumos)
    assert r["valor"] == 1.68 and r["classificacao"] == "verde", f"liquidez_corrente errado: {r}"
    assert "AC" in r["base_calculo"] and r["base_calculo"]["AC"] == 168000, "base de calculo nao rastreavel"
    print("  [ok] liquidez_corrente = 1.68 -> verde, base rastreavel (C3)")

    # 2. divida_liquida_ebitda = 2.1 -> amarelo
    r2 = calcular_kpi("divida_liquida_ebitda", insumos)
    assert r2["valor"] == 2.1 and r2["classificacao"] == "amarelo", f"dl/ebitda errado: {r2}"
    print("  [ok] divida_liquida_ebitda = 2.1 -> amarelo")

    # 3. ciclo_financeiro derivado (PMR+PME-PMP)
    r3 = calcular_kpi("ciclo_financeiro", insumos)
    # PMR = 80000/600000*30=4.0; PME=40000/360000*30=3.33; PMP=50000/300000*30=5.0; ciclo=2.33
    assert r3["valor"] is not None and r3["status"] == "ok", f"ciclo derivado falhou: {r3}"
    assert abs(r3["valor"] - 2.3) < 0.1, f"ciclo_financeiro fora do esperado: {r3['valor']}"
    print(f"  [ok] ciclo_financeiro derivado = {r3['valor']} dias (PMR+PME-PMP)")

    # 4. insumo faltante NAO inventa (premortem C3)
    r4 = calcular_kpi("liquidez_corrente", {"AC": 100000})  # falta PC
    assert r4["valor"] is None and r4["status"] == "insumo_faltante", f"deveria declarar falta: {r4}"
    assert "PC" in r4["insumos_faltantes"], "deveria listar PC como faltante"
    print("  [ok] insumo faltante -> valor None + declara faltante (NUNCA fabrica — C3)")

    # 5. divisao por zero -> indefinido, nao crash
    r5 = calcular_kpi("liquidez_corrente", {"AC": 100000, "PC": 0})
    assert r5["valor"] is None and r5["status"] == "indefinido_divisao_zero", f"div0 mal tratada: {r5}"
    print("  [ok] divisao por zero -> indefinido, sem crash")

    # 6. painel completo conta calculados vs faltantes
    painel = calcular_painel(insumos)
    assert painel["calculados"] >= 15, f"painel deveria calcular a maioria: {painel['calculados']}"
    print(f"  [ok] painel: {painel['calculados']}/{painel['total']} KPIs calculados")

    print("RESULTADO: kpi_engine.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(_auto_teste())
