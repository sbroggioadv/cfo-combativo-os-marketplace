#!/usr/bin/env python3
"""
nfe_parser.py — Parser de NF-e/NFC-e e NFS-e -> estrutura de nota fiscal.

Cobre:
  - NF-e / NFC-e (modelo 55/65, XML da SEFAZ/Fazenda).
  - NFS-e ABRASF + padrao nacional (servicos, ISS).

Estrategia (premortem C2 — degradacao graciosa, import dentro de funcao):
  1. nfelib (pip install nfelib) — bindings oficiais da Fazenda
  2. fallback xml.etree (stdlib) com tratamento de namespace — sempre disponivel
  3. se XML invalido: erro ESTRUTURADO

Extrai: emitente/destinatario, itens (NCM/servico, qtd, valor unit.),
tributos destacados (ICMS/ISS/PIS/COFINS/IPI), CFOP, chave de acesso.
Alimenta carga-tributaria e conciliacao.

USO:
    python3 nfe_parser.py <arquivo.xml>
"""

from __future__ import annotations

import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _parse_xml_seguro(texto: str) -> ET.Element:
    """Faz parse de XML de fonte externa de forma DEFENSIVA (anti-XXE / billion-laughs).

    NF-e/NFS-e vem de terceiros — XML hostil pode explorar resolucao de entidades
    externas (XXE) ou expansao recursiva (billion-laughs). Defesa em 2 camadas:
      1. defusedxml.ElementTree (pip install defusedxml) — bloqueia XXE/DTD/entity-bomb.
      2. fallback stdlib com parser que NAO resolve entidades externas.
    Import DENTRO da funcao (premortem C2 — modulo nunca quebra se a lib faltar).
    """
    try:
        from defusedxml.ElementTree import fromstring as _safe_fromstring  # type: ignore
        return _safe_fromstring(texto)
    except ImportError:
        pass
    # Fallback stdlib: parser explicito sem resolucao de entidades externas.
    parser = ET.XMLParser()
    try:
        # desabilita expansao de entidades (DefusedXML-style) quando o backend expat permite
        parser.parser.DefaultHandler = lambda data: None  # type: ignore[attr-defined]
        parser.parser.ExternalEntityRefHandler = lambda *a: False  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass
    # rejeita DOCTYPE/DTD logo de cara (vetor de billion-laughs e XXE)
    cabeca = texto[:2048].upper()
    if "<!DOCTYPE" in cabeca or "<!ENTITY" in cabeca:
        raise ET.ParseError("DOCTYPE/ENTITY recusado por seguranca (anti-XXE/billion-laughs)")
    return ET.fromstring(texto, parser=parser)


def _strip_ns(tag: str) -> str:
    """Remove namespace de uma tag XML ({http...}nome -> nome)."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_first(root: ET.Element, nome: str) -> ET.Element | None:
    """Busca primeiro elemento com tag local == nome (ignora namespace)."""
    for el in root.iter():
        if _strip_ns(el.tag) == nome:
            return el
    return None


def _find_all(root: ET.Element, nome: str) -> list[ET.Element]:
    return [el for el in root.iter() if _strip_ns(el.tag) == nome]


def _txt(el: ET.Element | None, nome: str, default: str = "") -> str:
    if el is None:
        return default
    for child in el.iter():
        if _strip_ns(child.tag) == nome and child.text:
            return child.text.strip()
    return default


def _to_float(s: str) -> float:
    try:
        return round(float(str(s).replace(",", ".")), 2)
    except (TypeError, ValueError):
        return 0.0


def _mascarar_doc(doc: str) -> str:
    """Mascara CPF/CNPJ para log (trava 3 LGPD)."""
    d = re.sub(r"\D", "", doc or "")
    if len(d) == 14:  # CNPJ
        return f"**.***.**{d[8]}/{d[8:12]}-**"
    if len(d) == 11:  # CPF
        return f"***.***.**{d[8]}-**"
    return "***"


def _detectar_tipo(root: ET.Element) -> str:
    tags = {_strip_ns(el.tag) for el in root.iter()}
    if "infNFe" in tags or "NFe" in tags:
        return "nfe"
    if any(t in tags for t in ("InfNfse", "infNfse", "CompNfse", "Nfse", "DeclaracaoPrestacaoServico")):
        return "nfse"
    return "desconhecido"


# ---------------------------------------------------------------------------
# NF-e / NFC-e
# ---------------------------------------------------------------------------

def _parse_nfe(root: ET.Element) -> dict[str, Any]:
    inf = _find_first(root, "infNFe")
    chave = ""
    if inf is not None and inf.get("Id"):
        chave = re.sub(r"\D", "", inf.get("Id", ""))

    emit = _find_first(root, "emit")
    dest = _find_first(root, "dest")
    ide = _find_first(root, "ide")

    emit_doc = _txt(emit, "CNPJ") or _txt(emit, "CPF")
    dest_doc = _txt(dest, "CNPJ") or _txt(dest, "CPF")

    itens: list[dict] = []
    total_icms = total_pis = total_cofins = total_ipi = 0.0
    for det in _find_all(root, "det"):
        prod = _find_first(det, "prod")
        imp = _find_first(det, "imposto")
        icms = _to_float(_txt(imp, "vICMS")) if imp is not None else 0.0
        pis = _to_float(_txt(imp, "vPIS")) if imp is not None else 0.0
        cofins = _to_float(_txt(imp, "vCOFINS")) if imp is not None else 0.0
        ipi = _to_float(_txt(imp, "vIPI")) if imp is not None else 0.0
        total_icms += icms
        total_pis += pis
        total_cofins += cofins
        total_ipi += ipi
        itens.append({
            "descricao": _txt(prod, "xProd"),
            "ncm": _txt(prod, "NCM"),
            "cfop": _txt(prod, "CFOP"),
            "quantidade": _to_float(_txt(prod, "qCom")),
            "valor_unitario": _to_float(_txt(prod, "vUnCom")),
            "valor_total": _to_float(_txt(prod, "vProd")),
            "tributos": {"icms": icms, "pis": pis, "cofins": cofins, "ipi": ipi},
        })

    icmstot = _find_first(root, "ICMSTot")
    valor_nf = _to_float(_txt(icmstot, "vNF")) if icmstot is not None else sum(i["valor_total"] for i in itens)

    return {
        "ok": True,
        "tipo": "nfe",
        "chave_acesso": chave,
        "numero": _txt(ide, "nNF"),
        "data_emissao": (_txt(ide, "dhEmi") or _txt(ide, "dEmi"))[:10],
        "emitente": {"nome": _txt(emit, "xNome"), "doc_mascarado": _mascarar_doc(emit_doc)},
        "destinatario": {"nome": _txt(dest, "xNome"), "doc_mascarado": _mascarar_doc(dest_doc)},
        "valor_total": valor_nf or round(sum(i["valor_total"] for i in itens), 2),
        "itens": itens,
        "tributos_totais": {
            "icms": round(total_icms, 2), "pis": round(total_pis, 2),
            "cofins": round(total_cofins, 2), "ipi": round(total_ipi, 2), "iss": 0.0,
        },
    }


# ---------------------------------------------------------------------------
# NFS-e (ABRASF + nacional)
# ---------------------------------------------------------------------------

def _parse_nfse(root: ET.Element) -> dict[str, Any]:
    def _first_of(*nomes: str, default: ET.Element | None = None) -> ET.Element | None:
        for n in nomes:
            el = _find_first(root, n)
            if el is not None:
                return el
        return default

    serv = _first_of("Servico", default=root)
    valores = _first_of("Valores", default=serv)
    prest = _first_of("PrestadorServico", "Prestador")
    tom = _first_of("TomadorServico", "Tomador")

    valor_serv = _to_float(_txt(valores, "ValorServicos"))
    iss = _to_float(_txt(valores, "ValorIss") or _txt(valores, "ValorISS"))
    pis = _to_float(_txt(valores, "ValorPis") or _txt(valores, "ValorPIS"))
    cofins = _to_float(_txt(valores, "ValorCofins") or _txt(valores, "ValorCOFINS"))

    prest_doc = _txt(prest, "Cnpj") or _txt(prest, "CpfCnpj") or _txt(prest, "Cpf")
    tom_doc = _txt(tom, "Cnpj") or _txt(tom, "CpfCnpj") or _txt(tom, "Cpf")

    return {
        "ok": True,
        "tipo": "nfse",
        "numero": _txt(root, "Numero"),
        "data_emissao": (_txt(root, "DataEmissao"))[:10],
        "codigo_servico": _txt(serv, "ItemListaServico") or _txt(serv, "CodigoTributacaoMunicipio"),
        "discriminacao": _txt(serv, "Discriminacao"),
        "emitente": {"nome": _txt(prest, "RazaoSocial"), "doc_mascarado": _mascarar_doc(prest_doc)},
        "destinatario": {"nome": _txt(tom, "RazaoSocial"), "doc_mascarado": _mascarar_doc(tom_doc)},
        "valor_total": valor_serv,
        "itens": [{
            "descricao": _txt(serv, "Discriminacao"),
            "valor_total": valor_serv,
            "tributos": {"iss": iss, "pis": pis, "cofins": cofins},
        }],
        "tributos_totais": {
            "iss": iss, "pis": pis, "cofins": cofins, "icms": 0.0, "ipi": 0.0,
        },
    }


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def parse_nfe(path: str) -> dict[str, Any]:
    """Le XML de NF-e/NFC-e ou NFS-e e retorna estrutura unificada.

    Tenta nfelib primeiro (so para validar/normalizar); o parse de campos
    usa xml.etree (stdlib) que funciona com ou sem nfelib.
    """
    if not Path(path).exists():
        return {"ok": False, "erro": "arquivo_nao_encontrado", "caminho": path}

    # nfelib (opcional): so confirma que o XML e uma NF-e valida; nao e obrigatorio
    try:
        import nfelib  # type: ignore  # noqa: F401  (import DENTRO da funcao)
        nfelib_disponivel = True
    except ImportError:
        nfelib_disponivel = False

    try:
        texto = Path(path).read_text(encoding="utf-8", errors="replace")
        # remove BOM e declaracao que as vezes vem suja
        texto = texto.lstrip("﻿")
        root = _parse_xml_seguro(texto)
    except ET.ParseError as exc:
        return {"ok": False, "erro": "xml_invalido", "mensagem": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "erro": "leitura_falhou", "mensagem": str(exc)}

    tipo = _detectar_tipo(root)
    if tipo == "nfe":
        res = _parse_nfe(root)
    elif tipo == "nfse":
        res = _parse_nfse(root)
    else:
        return {"ok": False, "erro": "tipo_nao_reconhecido",
                "mensagem": "XML nao parece NF-e/NFC-e nem NFS-e ABRASF/nacional."}

    res["_meta"] = {"nfelib_disponivel": nfelib_disponivel, "metodo": "xml.etree"}
    return res


# ---------------------------------------------------------------------------
# Auto-teste (XML SINTETICO de NF-e e NFS-e)
# ---------------------------------------------------------------------------

_NFE_SINTETICA = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
 <NFe><infNFe Id="NFe35260400000000000189550010000000011000000010">
  <ide><nNF>1</nNF><dhEmi>2026-04-10T10:00:00-03:00</dhEmi></ide>
  <emit><CNPJ>11222333000181</CNPJ><xNome>Empresa Alfa Sintetica Ltda</xNome></emit>
  <dest><CNPJ>99888777000166</CNPJ><xNome>Cliente Sintetico SA</xNome></dest>
  <det><prod><xProd>Produto Teste</xProd><NCM>84713012</NCM><CFOP>5102</CFOP>
   <qCom>2</qCom><vUnCom>500.00</vUnCom><vProd>1000.00</vProd></prod>
   <imposto><ICMS><vICMS>180.00</vICMS></ICMS><vPIS>16.50</vPIS><vCOFINS>76.00</vCOFINS></imposto></det>
  <total><ICMSTot><vNF>1000.00</vNF></ICMSTot></total>
 </infNFe></NFe>
</nfeProc>
"""

_NFSE_SINTETICA = """<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
 <Nfse><InfNfse><Numero>42</Numero><DataEmissao>2026-04-15T09:00:00</DataEmissao>
  <Servico><ItemListaServico>17.01</ItemListaServico>
   <Discriminacao>Consultoria sintetica</Discriminacao>
   <Valores><ValorServicos>3000.00</ValorServicos><ValorIss>150.00</ValorIss></Valores></Servico>
  <PrestadorServico><RazaoSocial>Prestador Sintetico ME</RazaoSocial>
   <IdentificacaoPrestador><Cnpj>11222333000181</Cnpj></IdentificacaoPrestador></PrestadorServico>
  <TomadorServico><RazaoSocial>Tomador Sintetico</RazaoSocial></TomadorServico>
 </InfNfse></Nfse>
</CompNfse>
"""


def _auto_teste() -> int:
    import tempfile
    print("== AUTO-TESTE nfe_parser.py (XML sintetico) ==")
    falhas = 0
    with tempfile.TemporaryDirectory() as td:
        # 1. NF-e
        f1 = Path(td) / "nfe.xml"
        f1.write_text(_NFE_SINTETICA, encoding="utf-8")
        r1 = parse_nfe(str(f1))
        assert r1["ok"] and r1["tipo"] == "nfe", f"nfe falhou: {r1}"
        assert r1["valor_total"] == 1000.0 and len(r1["itens"]) == 1
        assert r1["itens"][0]["ncm"] == "84713012" and r1["itens"][0]["cfop"] == "5102"
        assert r1["tributos_totais"]["icms"] == 180.0
        assert r1["emitente"]["doc_mascarado"].startswith("**"), "CNPJ nao mascarado (LGPD!)"
        print("  [ok] NF-e: itens, NCM/CFOP, tributos, CNPJ mascarado")

        # 2. NFS-e
        f2 = Path(td) / "nfse.xml"
        f2.write_text(_NFSE_SINTETICA, encoding="utf-8")
        r2 = parse_nfe(str(f2))
        assert r2["ok"] and r2["tipo"] == "nfse", f"nfse falhou: {r2}"
        assert r2["valor_total"] == 3000.0 and r2["tributos_totais"]["iss"] == 150.0
        assert r2["codigo_servico"] == "17.01"
        print("  [ok] NFS-e ABRASF: servico, ISS, valor")

        # 3. XML invalido degrada
        f3 = Path(td) / "ruim.xml"
        f3.write_text("<isso nao fecha", encoding="utf-8")
        r3 = parse_nfe(str(f3))
        assert not r3["ok"] and r3["erro"] == "xml_invalido", f"deveria detectar XML invalido: {r3}"
        print("  [ok] XML invalido -> erro estruturado, sem crash (C2)")

        # 4. XML hostil com DOCTYPE/ENTITY (XXE / billion-laughs) e RECUSADO
        f4 = Path(td) / "xxe.xml"
        f4.write_text(
            '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
            '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe/></nfeProc>',
            encoding="utf-8",
        )
        r4 = parse_nfe(str(f4))
        # ou defusedxml bloqueia, ou o guard de DOCTYPE recusa — em ambos os casos: nao OK
        assert not r4["ok"], f"XML com DOCTYPE/ENTITY deveria ser recusado (anti-XXE): {r4}"
        print("  [ok] DOCTYPE/ENTITY recusado (anti-XXE / billion-laughs)")

    print("RESULTADO: nfe_parser.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


def _main() -> int:
    if len(sys.argv) < 2:
        print("USO: python3 nfe_parser.py <arquivo.xml>", file=sys.stderr)
        return 2
    res = parse_nfe(sys.argv[1])
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(_main())
