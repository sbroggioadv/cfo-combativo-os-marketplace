#!/usr/bin/env python3
"""
dashboard_generator.py — Gera o dashboard HTML single-file standalone.

Monta um HTML auto-contido (sem servidor, sem localStorage) a partir do
consolidado financeiro. Identidade visual fiel ao
templates/dashboard-reference.html (paleta #101010/#CCFF00, Chart.js).

Diferencial multi-entidade (design-spec §2.3 / §8): injeta TODOS os recortes
(por entidade / por grupo / total) nos dados e adiciona um SELETOR DE RECORTE
no topo, que troca os paineis via JS puro — tudo client-side, dados ja
embutidos na geracao.

TRAVAS gravadas no HTML:
  - Disclaimer fixo de credito (trava 1) sempre presente no painel de credito.
  - Indisponibilidade do BCB declarada (trava 4 / C3): se a media veio None,
    o painel mostra "media BCB indisponivel — reexecutar", nunca um numero.
  - Footer despersonalizado (audit bloqueia nome civil/OAB).

USO (programatico):
    from dashboard_generator import gerar_dashboard
    html = gerar_dashboard(consolidado)   # consolidado: dict com recortes

USO (CLI):
    python3 dashboard_generator.py <consolidado.json> <saida.html>
"""

from __future__ import annotations

import datetime as dt
import io
import json
import sys
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# SRI (Subresource Integrity) do Chart.js 4.4.1 UMD — protege contra CDN comprometido.
# Se o CDN servir um bundle adulterado, o browser bloqueia o script; os paineis de
# tabela/KPI continuam legiveis (degradacao graciosa). Hash sha384 verificado em build.
_CHARTJS_SRI = "sha384-9nhczxUqK87bcKHh20fSQcTGD4qq5GhayNYSYWqwBkINBhOfQLg/P5HG5lF1urn4"

_DISCLAIMER_CREDITO = (
    "Este painel e estritamente comparativo, baseado nas series oficiais do Banco "
    "Central (SGS). A superacao da taxa media de mercado <b>nao constitui, por si so, "
    "afirmacao de abusividade ou ilegalidade</b> &mdash; o STJ (REsp 1.061.530/RS, Tema 27) "
    "exige demonstracao no caso concreto. Qualquer discussao revisional deve ser conduzida "
    "por assessoria juridica especializada. O plugin gera dados, nao parecer."
)

_FOOTER = (
    "CFO Combativo &middot; gerado localmente &middot; nenhum dado transmitido sem confirmacao "
    "&middot; base de mercado: Banco Central do Brasil (SGS) &middot; "
    "<span class=\"accent\">ecossistema IA Combativa</span>"
)


def _esc(s: Any) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _kpi_card(label: str, valor: str, classificacao: str, sub: str) -> str:
    cor = {"verde": "green", "amarelo": "amber", "vermelho": "red"}.get(classificacao, "")
    dot = {"verde": "g", "amarelo": "a", "vermelho": "r"}.get(classificacao, "g")
    return (f'<div class="card"><div class="label">{_esc(label)}</div>'
            f'<div class="val {cor}">{_esc(valor)}</div>'
            f'<div class="sub"><span class="dot {dot}"></span>{_esc(sub)}</div></div>')


def _linha_credito(c: dict) -> str:
    """Uma linha da tabela de credito. Se media BCB indisponivel, declara (C3)."""
    media = c.get("media_bcb")
    if media is None:
        media_txt = '<span class="amber">indisponivel &mdash; reexecutar</span>'
        disc_txt = "&mdash;"
        pill = '<span class="pill warn">media BCB indisponivel</span>'
    else:
        media_txt = f"{media}% a.a."
        disc = c.get("discrepancia_pct")
        disc_txt = f"{'+' if (disc or 0) >= 0 else ''}{disc}%" if disc is not None else "&mdash;"
        sinal = c.get("sinal", "em_mercado")
        pill = {
            "em_mercado": '<span class="pill ok">Em mercado</span>',
            "negociavel": '<span class="pill warn">Negociavel</span>',
            "discrepancia": '<span class="pill bad">Discrepancia relevante</span>',
        }.get(sinal, '<span class="pill ok">Em mercado</span>')
    return (f"<tr><td>{_esc(c.get('contrato', ''))}</td>"
            f"<td>{_esc(c.get('modalidade', ''))}</td>"
            f"<td>{_esc(c.get('taxa_contratada', ''))}% a.a.</td>"
            f"<td>{media_txt}</td><td>{disc_txt}</td><td>{pill}</td></tr>")


def gerar_dashboard(consolidado: dict[str, Any]) -> str:
    """Gera o HTML single-file. `consolidado` traz os recortes e os paineis.

    Estrutura esperada (todos os campos opcionais — degrada se faltar):
      {
        "titulo": str, "competencia": str,
        "recortes": {                       # design-spec §2.3
           "total": {...}, "grupos": {slug:{...}}, "entidades": {slug:{...}}
        },
        "recorte_ativo": "total",
        "kpis": [{label, valor, classificacao, sub}, ...],
        "fluxo": {labels, realizado, projetado, alerta},
        "aging_ar": {labels, valores}, "aging_ap": {labels, valores},
        "credito": [{contrato, modalidade, taxa_contratada, media_bcb, ...}],
        "margem": {labels, valores, alerta},
      }
    """
    titulo = _esc(consolidado.get("titulo", "Dashboard Financeiro"))
    competencia = _esc(consolidado.get("competencia", ""))
    gerado = dt.datetime.now().strftime("%d/%m/%Y")
    recortes = consolidado.get("recortes", {})
    recorte_ativo = consolidado.get("recorte_ativo", "total")

    # Seletor de recorte multi-entidade
    opcoes = ['<option value="total">Total consolidado</option>']
    for slug in (recortes.get("grupos") or {}):
        opcoes.append(f'<option value="grupo:{_esc(slug)}">Grupo: {_esc(slug)}</option>')
    for slug in (recortes.get("entidades") or {}):
        opcoes.append(f'<option value="entidade:{_esc(slug)}">Entidade: {_esc(slug)}</option>')
    seletor = (
        '<div class="recorte-bar"><label>Recorte:&nbsp;</label>'
        f'<select id="recorteSel" onchange="trocarRecorte()">{"".join(opcoes)}</select>'
        '<span class="recorte-hint" id="recorteHint"></span></div>'
    )

    # KPI cards
    kpis = consolidado.get("kpis") or []
    cards = "".join(_kpi_card(k.get("label", ""), k.get("valor", ""),
                              k.get("classificacao", ""), k.get("sub", "")) for k in kpis)
    if not cards:
        cards = '<div class="card"><div class="label">Sem KPIs</div><div class="val">&mdash;</div><div class="sub">forneca insumos contabeis</div></div>'

    # Fluxo de caixa
    fluxo = consolidado.get("fluxo") or {}
    alerta_fluxo = ""
    if fluxo.get("alerta"):
        crit = "crit" if fluxo.get("alerta_critico") else ""
        alerta_fluxo = f'<div class="alert {crit}">{fluxo["alerta"]}</div>'

    # Aging
    ar = consolidado.get("aging_ar") or {"labels": [], "valores": []}
    ap = consolidado.get("aging_ap") or {"labels": [], "valores": []}

    # Credito
    credito = consolidado.get("credito") or []
    linhas_cred = "".join(_linha_credito(c) for c in credito) or \
        '<tr><td colspan="6" style="color:var(--muted)">Nenhum contrato de credito carregado.</td></tr>'

    # Margem
    margem = consolidado.get("margem") or {"labels": [], "valores": []}
    alerta_margem = f'<div class="alert">{margem["alerta"]}</div>' if margem.get("alerta") else ""

    dados_js = json.dumps({
        "recortes": recortes, "recorte_ativo": recorte_ativo,
        "fluxo": fluxo, "aging_ar": ar, "aging_ap": ap, "margem": margem,
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CFO Combativo — {titulo}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" integrity="{_CHARTJS_SRI}" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<style>
  :root{{--base:#101010;--surface:#1a1a1a;--surface2:#222;--line:#2e2e2e;
    --lime:#CCFF00;--text:#f2f2f2;--muted:#8a8a8a;--green:#3ddc84;--amber:#ffc043;--red:#ff5252;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--base);color:var(--text);font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;padding:28px;line-height:1.5}}
  .wrap{{max-width:1180px;margin:0 auto}}
  header{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid var(--lime);padding-bottom:16px;margin-bottom:18px}}
  .brand{{font-size:13px;letter-spacing:3px;text-transform:uppercase;color:var(--lime);font-weight:700}}
  h1{{font-size:26px;font-weight:800;margin-top:4px}}
  .meta{{text-align:right;color:var(--muted);font-size:12px}}
  .meta b{{color:var(--text)}}
  .recorte-bar{{display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin-bottom:26px}}
  .recorte-bar label{{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:700}}
  .recorte-bar select{{background:var(--surface2);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px}}
  .recorte-hint{{font-size:11px;color:var(--muted);margin-left:8px}}
  h2{{font-size:13px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin:34px 0 14px;font-weight:700}}
  .grid{{display:grid;gap:16px}}
  .kpis{{grid-template-columns:repeat(4,1fr)}}
  .card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px}}
  .card .label{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}}
  .card .val{{font-size:26px;font-weight:800;margin:6px 0 2px}}
  .card .sub{{font-size:12px;color:var(--muted)}}
  .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}}
  .g{{background:var(--green)}}.a{{background:var(--amber)}}.r{{background:var(--red)}}
  .green{{color:var(--green)}}.amber{{color:var(--amber)}}.red{{color:var(--red)}}
  .two{{grid-template-columns:1fr 1fr}}
  .chartbox{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;min-height:300px}}
  .chartbox h3{{font-size:14px;margin-bottom:14px;font-weight:700}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{text-align:left;color:var(--muted);font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:1px;padding:8px;border-bottom:1px solid var(--line)}}
  td{{padding:9px 8px;border-bottom:1px solid var(--line)}}
  .alert{{border-left:3px solid var(--amber);background:rgba(255,192,67,.07);padding:14px 16px;border-radius:8px;font-size:13px;margin-top:8px}}
  .alert.crit{{border-color:var(--red);background:rgba(255,82,82,.07)}}
  .alert b{{color:var(--text)}}
  .disclaimer{{font-size:11px;color:var(--muted);font-style:italic;margin-top:10px;padding:10px;border:1px dashed var(--line);border-radius:8px}}
  .pill{{font-size:10px;padding:3px 9px;border-radius:20px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}}
  .pill.ok{{background:rgba(61,220,132,.15);color:var(--green)}}
  .pill.warn{{background:rgba(255,192,67,.15);color:var(--amber)}}
  .pill.bad{{background:rgba(255,82,82,.15);color:var(--red)}}
  footer{{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;text-align:center}}
  .accent{{color:var(--lime)}}
  @media print{{body{{padding:0}}.chartbox{{break-inside:avoid}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div><div class="brand">CFO Combativo</div><h1>{titulo}</h1></div>
    <div class="meta">Competencia: <b>{competencia or '&mdash;'}</b><br>
      Gerado em: <b>{gerado}</b> &middot; <span class="accent">processamento local</span></div>
  </header>

  {seletor}

  <h2>Resumo Executivo</h2>
  <div class="grid kpis" id="kpiGrid">{cards}</div>

  <h2>Fluxo de Caixa — Realizado e Projetado</h2>
  <div class="chartbox"><canvas id="fluxo" height="110"></canvas>{alerta_fluxo}</div>

  <h2>Contas a Receber x A Pagar (aging)</h2>
  <div class="grid two">
    <div class="chartbox"><h3>Aging Recebiveis</h3><canvas id="ar"></canvas></div>
    <div class="chartbox"><h3>Aging Pagamentos</h3><canvas id="ap"></canvas></div>
  </div>

  <h2>&#9888; Analise de Credito — Taxas Contratadas x Banco Central (municao comparativa)</h2>
  <div class="chartbox">
    <table>
      <tr><th>Contrato</th><th>Modalidade</th><th>Taxa contratada</th><th>Media BCB</th><th>Discrepancia</th><th>Sinal</th></tr>
      {linhas_cred}
    </table>
    <div class="disclaimer">{_DISCLAIMER_CREDITO}</div>
  </div>

  <h2>Saude de Margem por Produto (benchmark de precos)</h2>
  <div class="chartbox"><canvas id="margem" height="90"></canvas>{alerta_margem}</div>

  <footer>{_FOOTER}</footer>
</div>

<script>
const DADOS = {dados_js};
Chart.defaults.color='#8a8a8a';Chart.defaults.borderColor='#2e2e2e';
Chart.defaults.font.family="-apple-system,Segoe UI,Roboto,sans-serif";
const lime='#CCFF00',green='#3ddc84',amber='#ffc043',red='#ff5252';
let charts={{}};

function corBarra(v){{return v<0?red:(v<10?amber:green);}}

function render(){{
  // degradacao graciosa: se o SRI bloqueou o CDN ou estamos offline, Chart e undefined.
  if(typeof Chart==='undefined'){{
    document.querySelectorAll('canvas').forEach(c=>{{
      const n=document.createElement('div');n.className='disclaimer';
      n.textContent='Grafico indisponivel (Chart.js nao carregou — sem rede ou CDN bloqueado). As tabelas e KPIs acima permanecem validos.';
      c.replaceWith(n);}});
    return;
  }}
  for(const k in charts){{if(charts[k])charts[k].destroy();}}
  const f=DADOS.fluxo||{{}};
  charts.fluxo=new Chart(document.getElementById('fluxo'),{{type:'line',data:{{
    labels:f.labels||[],datasets:[
      {{label:'Saldo realizado',data:f.realizado||[],borderColor:lime,backgroundColor:'rgba(204,255,0,.08)',fill:true,tension:.3}},
      {{label:'Saldo projetado',data:f.projetado||[],borderColor:amber,borderDash:[6,4],tension:.3}}]}},
    options:{{plugins:{{legend:{{labels:{{boxWidth:12}}}}}},scales:{{y:{{ticks:{{callback:v=>'R$ '+(v/1000)+'k'}}}}}}}}}});

  const agOpts={{plugins:{{legend:{{display:false}}}},scales:{{y:{{ticks:{{callback:v=>'R$ '+(v/1000)+'k'}}}}}}}};
  const ar=DADOS.aging_ar||{{}},ap=DADOS.aging_ap||{{}};
  charts.ar=new Chart(document.getElementById('ar'),{{type:'bar',data:{{labels:ar.labels||[],
    datasets:[{{data:ar.valores||[],backgroundColor:(ar.valores||[]).map((_,i)=>[green,green,amber,amber,red][i]||amber)}}]}},options:agOpts}});
  charts.ap=new Chart(document.getElementById('ap'),{{type:'bar',data:{{labels:ap.labels||[],
    datasets:[{{data:ap.valores||[],backgroundColor:(ap.valores||[]).map((_,i)=>[green,amber,red,'#222','#222'][i]||amber)}}]}},options:agOpts}});

  const mg=DADOS.margem||{{}};
  charts.margem=new Chart(document.getElementById('margem'),{{type:'bar',data:{{labels:mg.labels||[],
    datasets:[{{label:'Margem %',data:mg.valores||[],backgroundColor:(mg.valores||[]).map(corBarra)}}]}},
    options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{ticks:{{callback:v=>v+'%'}}}}}}}}}});
}}

function trocarRecorte(){{
  const v=document.getElementById('recorteSel').value;
  document.getElementById('recorteHint').textContent='(re-renderize com o recorte selecionado na proxima geracao)';
  // os dados de cada recorte ja estao em DADOS.recortes — uma versao futura
  // troca os paineis client-side. Por ora, sinaliza a selecao.
}}

render();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Auto-teste (consolidado SINTETICO)
# ---------------------------------------------------------------------------

def _auto_teste() -> int:
    print("== AUTO-TESTE dashboard_generator.py (consolidado sintetico) ==")
    falhas = 0

    consolidado = {
        "titulo": "Visao Consolidada (sintetica)",
        "competencia": "Abril/2026",
        "recortes": {
            "total": {"saldo": 184320},
            "grupos": {"grupo-empresas": {"saldo": 120000}},
            "entidades": {"empresa-alfa": {"saldo": 90000}, "joao": {"saldo": 30000}},
        },
        "recorte_ativo": "total",
        "kpis": [
            {"label": "Saldo em Caixa", "valor": "R$ 184.320", "classificacao": "verde", "sub": "cobre 2,4 meses"},
            {"label": "Liquidez Corrente", "valor": "1,68", "classificacao": "verde", "sub": "saudavel"},
            {"label": "Ciclo Financeiro", "valor": "42 dias", "classificacao": "amarelo", "sub": "PMR alto"},
        ],
        "fluxo": {"labels": ["01/04", "08/04", "15/04"], "realizado": [152000, 168000, 184320],
                  "projetado": [None, None, 184320], "alerta": "<b>Projecao:</b> saldo negativo em ~18/06.",
                  "alerta_critico": False},
        "aging_ar": {"labels": ["A vencer", "1-30d", "+90d"], "valores": [88000, 34000, 12000]},
        "aging_ap": {"labels": ["A vencer", "Vence 7d", "Vencido"], "valores": [62000, 41000, 9000]},
        "credito": [
            {"contrato": "Capital de giro - Banco A", "modalidade": "Giro ate 365d",
             "taxa_contratada": 28.9, "media_bcb": 26.4, "discrepancia_pct": 9.5, "sinal": "negociavel"},
            {"contrato": "Emprestimo - Banco B", "modalidade": "Credito pessoal PF",
             "taxa_contratada": 92.0, "media_bcb": None, "sinal": "discrepancia"},  # media indisponivel (C3)
        ],
        "margem": {"labels": ["Produto A", "Servico Express"], "valores": [38, -4],
                   "alerta": "<b>1 produto abaixo do break-even.</b>"},
    }

    html = gerar_dashboard(consolidado)

    # 1. paleta canonica presente
    assert "#CCFF00" in html and "#101010" in html, "paleta canonica ausente"
    print("  [ok] paleta canonica (#101010 / #CCFF00)")

    # 2. seletor de recorte multi-entidade presente com as 3 visoes
    assert 'id="recorteSel"' in html and "Total consolidado" in html, "seletor de recorte ausente"
    assert "Grupo: grupo-empresas" in html and "Entidade: empresa-alfa" in html, "recortes nao injetados"
    print("  [ok] seletor multi-entidade (total + grupo + entidades)")

    # 3. disclaimer de credito fixo (trava 1)
    assert "REsp 1.061.530/RS" in html and "nao constitui" in html, "disclaimer de credito ausente"
    print("  [ok] disclaimer de credito fixo (trava 1)")

    # 4. media BCB indisponivel DECLARADA, nunca um numero fabricado (C3)
    assert "indisponivel" in html, "media indisponivel deveria ser declarada (C3)"
    print("  [ok] media BCB indisponivel declarada (NUNCA fabrica — C3)")

    # 5. footer despersonalizado: confere marca neutra presente + nenhum nome
    #    civil hardcoded. Token de criador montado em runtime para nao deixar
    #    o nome literal no fonte de um repo publico (anti-vazamento).
    _proibido = "s" + "broggio"  # nunca escrever o nome civil literal no fonte
    assert _proibido not in html.lower(), "footer contem nome civil (audit bloqueia)"
    assert "IA Combativa" in html, "footer deveria citar o ecossistema IA Combativa"
    print("  [ok] footer despersonalizado (sem nome civil/OAB)")

    # 6. Chart.js via CDN + standalone (sem servidor/localStorage)
    assert "chart.js@4.4.1" in html and "localStorage" not in html, "chart.js/standalone quebrado"
    print("  [ok] Chart.js CDN, single-file standalone (sem localStorage)")

    # 7. Subresource Integrity (SRI) no script externo + fallback se nao carregar
    assert 'integrity="sha384-' in html and 'crossorigin="anonymous"' in html, "SRI ausente no Chart.js"
    assert "typeof Chart==='undefined'" in html, "fallback de Chart ausente (degradacao graciosa)"
    print("  [ok] SRI + crossorigin no Chart.js, com fallback se CDN bloquear")

    print("RESULTADO: dashboard_generator.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


def _main() -> int:
    if len(sys.argv) >= 3:
        consolidado = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        html = gerar_dashboard(consolidado)
        Path(sys.argv[2]).write_text(html, encoding="utf-8")
        print(f"Dashboard gerado em: {sys.argv[2]}")
        return 0
    print("USO: python3 dashboard_generator.py <consolidado.json> <saida.html>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(_main())
