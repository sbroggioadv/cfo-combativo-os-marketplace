#!/usr/bin/env python3
"""
state.py — Maquina de estados do cfo-state.json (grafo multi-entidade).

Adaptado da maquinaria do calculosjudiciais/state.py. Mesma estrutura
(load/save/validate/migrate/backup/CLI), mas:
- STATE_DIR = ".cfo"          (workdir do operador, fora do plugin, NUNCA versionado)
- STATE_FILENAME = "cfo-state.json"
- create_empty() e o schema seguem o STATE SCHEMA do design-spec  6.

Modelo multi-entidade (design-spec  2): grafo de ENTIDADES (PF/PJ) cada uma
com N CONTAS, agrupaveis em GRUPOS opcionais. Append-only: editar o grafo
nunca apaga o que ja existe, so agrega (trava  2.4).

CLI:
    python3 scripts/state.py init <workdir>
    python3 scripts/state.py validate <workdir>
    python3 scripts/state.py show <workdir>
    python3 scripts/state.py set <workdir> <json_path> <value>
    python3 scripts/state.py migrate <workdir>

Nao depende de bibliotecas externas obrigatorias. Se 'jsonschema' estiver
instalado, validacao e completa; senao, validacao minima (campos obrigatorios
+ tipos basicos + regras do grafo).

LGPD (trava  3 / premortem C4): este arquivo vive em <cwd>/.cfo/ e esta no
.gitignore. Nunca grava saldo/conta/CPF em log em texto plano.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import shutil
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCHEMA_VERSION = "1.0.0"
PLUGIN_VERSION = "0.1.0"
STATE_FILENAME = "cfo-state.json"
STATE_DIR = ".cfo"

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PERFIS = ("pf", "pj", "ambos")
_TIPO_ENTIDADE = ("pf", "pj")
_TIPO_CONTA = ("cc", "cartao", "investimento")
_REGIMES = ("simples", "presumido", "real", None)

try:
    import jsonschema  # type: ignore
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _schema_path() -> Path:
    return Path(__file__).parent / "state-schema.json"


def _state_file(workdir: Path) -> Path:
    return workdir / STATE_DIR / STATE_FILENAME


def _backup_file(workdir: Path) -> Path:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return workdir / STATE_DIR / ".backup" / f"cfo-state.{ts}.json"


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def load(workdir: Path) -> dict:
    """Le cfo-state.json. Valida. Retorna dict."""
    sf = _state_file(workdir)
    if not sf.exists():
        raise FileNotFoundError(f"Arquivo de estado nao encontrado: {sf}")
    state = json.loads(sf.read_text(encoding="utf-8"))
    errors = validate(state)
    if errors:
        raise ValueError(f"State invalido em {sf}:\n  " + "\n  ".join(errors))
    return state


def save(workdir: Path, state: dict, *, create_backup: bool = True) -> Path:
    """Valida state, cria backup do anterior (trava append-only C8), escreve atomicamente."""
    errors = validate(state)
    if errors:
        raise ValueError("State invalido — nao salvo:\n  " + "\n  ".join(errors))

    state["updated_at"] = _now_iso()

    sf = _state_file(workdir)
    sf.parent.mkdir(parents=True, exist_ok=True)

    if create_backup and sf.exists():
        bf = _backup_file(workdir)
        bf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sf, bf)

    tmp = sf.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(sf)
    return sf


def create_empty(workdir: Path, *, perfil: str = "ambos",
                 plugin_version: str = PLUGIN_VERSION) -> dict:
    """Cria state inicial vazio (grafo a montar via cfo-onboarding). Nao salva em disco."""
    if perfil not in _PERFIS:
        perfil = "ambos"
    now = _now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_version": plugin_version,
        "created_at": now,
        "updated_at": now,
        "workdir": str(workdir),
        "perfil": perfil,
        "entidades": [],
        "grupos": [],
        "contabilidade": {
            "nome": None,
            "email": None,
            "avisar_antes_envio": True,
        },
        "tools": {
            "email_provider": None,
            "banco_psp": None,
            "contabilidade_sistema": None,
            "outras": [],
        },
        "preferences": {
            "idioma": "pt-BR",
            "moeda": "BRL",
            "recorte_default": "total",
            "lgpd_aviso_aceito": False,
            "mascarar_em_log": True,
        },
        "metas": [],
        "wizard_state": {
            "completed": False,
            "current_step": "perfil",
            "completed_steps": [],
            "last_interaction_at": now,
        },
    }


# ---------------------------------------------------------------------------
# Helpers do grafo (append-only — trava  2.4 / premortem C8)
# ---------------------------------------------------------------------------

def add_entidade(state: dict, entidade: dict) -> dict:
    """Adiciona/atualiza entidade no grafo SEM apagar as existentes (append-only).

    Se ja existe entidade com mesmo id, faz merge dos campos novos + contas
    (uniao por conta.id). Nunca remove contas/entidades — so agrega.
    """
    entidade = dict(entidade)
    entidade.setdefault("contas", [])
    ents = state.setdefault("entidades", [])
    for ex in ents:
        if ex.get("id") == entidade.get("id"):
            # merge: campos escalares atualizam, contas se unem por id
            contas_existentes = {c.get("id"): c for c in ex.get("contas", [])}
            for c in entidade.get("contas", []):
                contas_existentes[c.get("id")] = {**contas_existentes.get(c.get("id"), {}), **c}
            ex.update({k: v for k, v in entidade.items() if k != "contas"})
            ex["contas"] = list(contas_existentes.values())
            return state
    ents.append(entidade)
    return state


def add_grupo(state: dict, grupo: dict) -> dict:
    """Adiciona grupo (idempotente por id)."""
    grupos = state.setdefault("grupos", [])
    for g in grupos:
        if g.get("id") == grupo.get("id"):
            g.update(grupo)
            return state
    grupos.append(dict(grupo))
    return state


def entidades_do_grupo(state: dict, grupo_id: str) -> list[str]:
    """Lista ids das entidades pertencentes a um grupo."""
    return [e["id"] for e in state.get("entidades", []) if e.get("grupo_id") == grupo_id]


# ---------------------------------------------------------------------------
# Validacao
# ---------------------------------------------------------------------------

def validate(state: dict) -> list[str]:
    """Valida state contra schema. Retorna lista de erros (vazia = OK)."""
    errors: list[str] = []

    if HAS_JSONSCHEMA and _schema_path().exists():
        try:
            schema = json.loads(_schema_path().read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            for err in sorted(validator.iter_errors(state), key=lambda e: list(e.path)):
                path = " / ".join(str(p) for p in err.absolute_path) or "(root)"
                errors.append(f"{path}: {err.message}")
            # mesmo com jsonschema, rodamos as regras semanticas do grafo
            errors.extend(_validate_grafo(state))
            return errors
        except Exception as e:  # noqa: BLE001
            errors.append(f"Validacao via jsonschema falhou ({e}); usando fallback minimo.")

    # Fallback minimo (stdlib only)
    required_top = [
        "schema_version", "created_at", "updated_at", "perfil",
        "entidades", "grupos", "preferences", "wizard_state",
    ]
    for field in required_top:
        if field not in state:
            errors.append(f"Campo obrigatorio ausente: {field}")

    if state.get("perfil") not in _PERFIS:
        errors.append(f"perfil: '{state.get('perfil')}' invalido (use pf|pj|ambos)")

    for col in ("entidades", "grupos", "metas"):
        if col in state and not isinstance(state[col], list):
            errors.append(f"{col}: deve ser lista")

    errors.extend(_validate_grafo(state))
    return errors


def _validate_grafo(state: dict) -> list[str]:
    """Regras semanticas do grafo multi-entidade (rodam sempre)."""
    errors: list[str] = []
    grupo_ids = {g.get("id") for g in state.get("grupos", []) if isinstance(g, dict)}
    ent_ids: set[str] = set()
    conta_ids: set[str] = set()

    for i, ent in enumerate(state.get("entidades", [])):
        if not isinstance(ent, dict):
            errors.append(f"entidades[{i}]: deve ser objeto")
            continue
        eid = ent.get("id")
        if not eid or not _SLUG_RE.match(str(eid)):
            errors.append(f"entidades[{i}].id: '{eid}' nao e slug valido (a-z, 0-9, hifen)")
        elif eid in ent_ids:
            errors.append(f"entidades[{i}].id: '{eid}' duplicado")
        else:
            ent_ids.add(eid)

        if ent.get("tipo") not in _TIPO_ENTIDADE:
            errors.append(f"entidades[{i}].tipo: '{ent.get('tipo')}' invalido (pf|pj)")

        if ent.get("tipo") == "pj" and ent.get("regime_tributario") not in _REGIMES:
            errors.append(
                f"entidades[{i}].regime_tributario: "
                f"'{ent.get('regime_tributario')}' invalido (simples|presumido|real|null)"
            )

        gid = ent.get("grupo_id")
        if gid is not None and gid not in grupo_ids:
            errors.append(f"entidades[{i}].grupo_id: '{gid}' nao existe em grupos[]")

        for j, conta in enumerate(ent.get("contas", []) or []):
            if not isinstance(conta, dict):
                errors.append(f"entidades[{i}].contas[{j}]: deve ser objeto")
                continue
            cid = conta.get("id")
            if not cid or not _SLUG_RE.match(str(cid)):
                errors.append(f"entidades[{i}].contas[{j}].id: '{cid}' nao e slug valido")
            elif cid in conta_ids:
                errors.append(f"entidades[{i}].contas[{j}].id: '{cid}' duplicado no grafo")
            else:
                conta_ids.add(cid)
            if conta.get("tipo") and conta.get("tipo") not in _TIPO_CONTA:
                errors.append(
                    f"entidades[{i}].contas[{j}].tipo: '{conta.get('tipo')}' invalido (cc|cartao|investimento)"
                )

    for i, g in enumerate(state.get("grupos", [])):
        if not isinstance(g, dict):
            errors.append(f"grupos[{i}]: deve ser objeto")
            continue
        if not g.get("id") or not _SLUG_RE.match(str(g.get("id"))):
            errors.append(f"grupos[{i}].id: '{g.get('id')}' nao e slug valido")

    return errors


# ---------------------------------------------------------------------------
# Migracao
# ---------------------------------------------------------------------------

def migrate(state: dict) -> tuple[dict, bool]:
    """Migra state para SCHEMA_VERSION atual. Retorna (state_novo, mudou).

    v0.x -> 1.0.0: garante presenca dos blocos canonicos (idempotente).
    """
    from_v = state.get("schema_version", "0.0.0")
    if from_v == SCHEMA_VERSION:
        return state, False

    state.setdefault("perfil", "ambos")
    state.setdefault("entidades", [])
    state.setdefault("grupos", [])
    state.setdefault("metas", [])
    state.setdefault("contabilidade", {"nome": None, "email": None, "avisar_antes_envio": True})
    state.setdefault("tools", {
        "email_provider": None, "banco_psp": None,
        "contabilidade_sistema": None, "outras": [],
    })
    prefs = state.setdefault("preferences", {})
    prefs.setdefault("idioma", "pt-BR")
    prefs.setdefault("moeda", "BRL")
    prefs.setdefault("recorte_default", "total")
    prefs.setdefault("lgpd_aviso_aceito", False)
    prefs.setdefault("mascarar_em_log", True)
    ws = state.setdefault("wizard_state", {})
    ws.setdefault("completed", False)
    ws.setdefault("current_step", "perfil")
    ws.setdefault("completed_steps", [])

    state["schema_version"] = SCHEMA_VERSION
    return state, True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_init(args: argparse.Namespace) -> int:
    wd = Path(args.workdir).resolve()
    if _state_file(wd).exists() and not args.force:
        print(f"ERRO: {_state_file(wd)} ja existe. Use --force para sobrescrever.")
        return 1
    state = create_empty(wd, perfil=args.perfil or "ambos")
    sf = save(wd, state, create_backup=False)
    print(f"State criado em: {sf}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    wd = Path(args.workdir).resolve()
    try:
        load(wd)
        print("OK: state valido.")
        return 0
    except (FileNotFoundError, ValueError) as e:
        print(f"ERRO: {e}")
        return 1


def _cmd_show(args: argparse.Namespace) -> int:
    wd = Path(args.workdir).resolve()
    state = load(wd)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    wd = Path(args.workdir).resolve()
    state = load(wd)
    keys = args.json_path.split(".")
    node = state
    for k in keys[:-1]:
        if k not in node or not isinstance(node[k], dict):
            node[k] = {}
        node = node[k]
    try:
        value = json.loads(args.value)
    except json.JSONDecodeError:
        value = args.value
    node[keys[-1]] = value
    save(wd, state)
    print(f"OK: {args.json_path} = {value!r}")
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    wd = Path(args.workdir).resolve()
    state = json.loads(_state_file(wd).read_text(encoding="utf-8"))
    new_state, changed = migrate(state)
    if changed:
        save(wd, new_state)
        print(f"OK: migrado para schema {SCHEMA_VERSION}.")
    else:
        print(f"Ja na versao {SCHEMA_VERSION}, nada a fazer.")
    return 0


def _cmd_add_entidade(args: argparse.Namespace) -> int:
    """Agrega entidade ao grafo (append-only — nunca apaga as existentes)."""
    wd = Path(args.workdir).resolve()
    state = load(wd)
    entidade = {
        "id": args.id, "tipo": args.tipo, "nome": args.nome,
        "doc_mascarado": args.doc, "regime_tributario": args.regime,
        "grupo_id": args.grupo, "inicio": args.inicio, "contas": [],
    }
    # remove chaves None para nao poluir o grafo
    entidade = {k: v for k, v in entidade.items() if v is not None or k == "contas"}
    add_entidade(state, entidade)
    save(wd, state)
    print(f"OK: entidade '{args.id}' agregada (append-only). Total: {len(state.get('entidades', []))} entidade(s).")
    return 0


def _cmd_add_conta(args: argparse.Namespace) -> int:
    """Agrega conta a uma entidade existente (append-only por id de conta)."""
    wd = Path(args.workdir).resolve()
    state = load(wd)
    conta = {"id": args.id, "banco": args.banco, "tipo": args.tipo, "apelido": args.apelido}
    conta = {k: v for k, v in conta.items() if v is not None}
    add_entidade(state, {"id": args.entidade, "contas": [conta]})
    save(wd, state)
    print(f"OK: conta '{args.id}' agregada a entidade '{args.entidade}' (append-only).")
    return 0


def _cmd_add_grupo(args: argparse.Namespace) -> int:
    """Agrega grupo ao grafo (idempotente por id)."""
    wd = Path(args.workdir).resolve()
    state = load(wd)
    grupo = {"id": args.id, "nome": args.nome, "tipo": args.tipo}
    grupo = {k: v for k, v in grupo.items() if v is not None}
    add_grupo(state, grupo)
    save(wd, state)
    print(f"OK: grupo '{args.id}' agregado. Total: {len(state.get('grupos', []))} grupo(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Maquina de estados cfo-state.json (grafo multi-entidade)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Cria state inicial vazio.")
    p_init.add_argument("workdir")
    p_init.add_argument("--perfil", choices=_PERFIS)
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=_cmd_init)

    p_validate = sub.add_parser("validate", help="Valida state existente.")
    p_validate.add_argument("workdir")
    p_validate.set_defaults(func=_cmd_validate)

    p_show = sub.add_parser("show", help="Imprime state como JSON.")
    p_show.add_argument("workdir")
    p_show.set_defaults(func=_cmd_show)

    p_set = sub.add_parser("set", help="Define campo. Ex: set ./ preferences.recorte_default total")
    p_set.add_argument("workdir")
    p_set.add_argument("json_path")
    p_set.add_argument("value")
    p_set.set_defaults(func=_cmd_set)

    p_migrate = sub.add_parser("migrate", help="Migra state para SCHEMA_VERSION atual.")
    p_migrate.add_argument("workdir")
    p_migrate.set_defaults(func=_cmd_migrate)

    p_ent = sub.add_parser("add-entidade", help="Agrega entidade ao grafo (append-only).")
    p_ent.add_argument("workdir")
    p_ent.add_argument("--id", required=True, help="slug kebab-case da entidade")
    p_ent.add_argument("--tipo", required=True, choices=["pf", "pj"])
    p_ent.add_argument("--nome", required=True)
    p_ent.add_argument("--doc", help="CPF/CNPJ MASCARADO (nunca completo)")
    p_ent.add_argument("--regime", help="simples|presumido|real (PJ)")
    p_ent.add_argument("--grupo", help="id do grupo (opcional)")
    p_ent.add_argument("--inicio", help="YYYY-MM")
    p_ent.set_defaults(func=_cmd_add_entidade)

    p_conta = sub.add_parser("add-conta", help="Agrega conta a uma entidade (append-only).")
    p_conta.add_argument("workdir")
    p_conta.add_argument("--entidade", required=True, help="id da entidade dona")
    p_conta.add_argument("--id", required=True, help="slug da conta")
    p_conta.add_argument("--banco", required=True)
    p_conta.add_argument("--tipo", default="cc", choices=["cc", "cartao", "investimento"])
    p_conta.add_argument("--apelido")
    p_conta.set_defaults(func=_cmd_add_conta)

    p_grp = sub.add_parser("add-grupo", help="Agrega grupo ao grafo (idempotente).")
    p_grp.add_argument("workdir")
    p_grp.add_argument("--id", required=True)
    p_grp.add_argument("--nome", required=True)
    p_grp.add_argument("--tipo", choices=["pf", "pj", "misto"])
    p_grp.set_defaults(func=_cmd_add_grupo)

    args = parser.parse_args()
    return args.func(args)


# ---------------------------------------------------------------------------
# Auto-teste (dado SINTETICO — premortem C8: append-only nao destroi historico)
# ---------------------------------------------------------------------------

def _auto_teste() -> int:
    import tempfile
    print("== AUTO-TESTE state.py (dado sintetico) ==")
    falhas = 0
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)

        # 1. create_empty + save + load
        st = create_empty(wd, perfil="ambos")
        save(wd, st, create_backup=False)
        st = load(wd)
        assert st["perfil"] == "ambos", "perfil nao persistiu"
        print("  [ok] create_empty / save / load")

        # 2. grafo: grupo + 2 entidades + contas (append-only)
        add_grupo(st, {"id": "grupo-empresas", "nome": "Grupo de Empresas", "tipo": "pj"})
        add_entidade(st, {
            "id": "empresa-alfa", "tipo": "pj", "nome": "Empresa Alfa Sintetica",
            "doc_mascarado": "**.***.**8/0001-**", "regime_tributario": "simples",
            "grupo_id": "grupo-empresas", "inicio": "2026-01",
            "contas": [{"id": "itau-cc-001", "banco": "itau", "tipo": "cc", "apelido": "Itau PJ"}],
        })
        save(wd, st)
        st = load(wd)
        assert len(st["entidades"]) == 1, "entidade A nao gravou"
        print("  [ok] add_grupo / add_entidade A")

        # 3. agregar entidade B NAO apaga A (premortem C8)
        add_entidade(st, {
            "id": "joao-sintetico", "tipo": "pf", "nome": "Joao Sintetico",
            "doc_mascarado": "***.***.**8-**", "grupo_id": None, "inicio": "2026-03",
            "contas": [{"id": "nubank-001", "banco": "nubank", "tipo": "cc", "apelido": "Nubank"}],
        })
        save(wd, st)
        st = load(wd)
        ids = {e["id"] for e in st["entidades"]}
        assert ids == {"empresa-alfa", "joao-sintetico"}, f"append-only quebrou: {ids}"
        print("  [ok] agregar B preservou A (append-only)")

        # 4. merge de conta nova na entidade existente nao remove conta antiga
        add_entidade(st, {
            "id": "empresa-alfa", "tipo": "pj", "nome": "Empresa Alfa Sintetica",
            "contas": [{"id": "bb-cc-002", "banco": "bb", "tipo": "cc", "apelido": "BB PJ"}],
        })
        alfa = next(e for e in st["entidades"] if e["id"] == "empresa-alfa")
        assert {c["id"] for c in alfa["contas"]} == {"itau-cc-001", "bb-cc-002"}, "merge de conta perdeu conta antiga"
        print("  [ok] merge de conta preservou conta existente")

        # 5. validacao do grafo pega grupo_id invalido
        st_ruim = create_empty(wd)
        st_ruim["entidades"] = [{"id": "x", "tipo": "pj", "grupo_id": "inexistente", "contas": []}]
        errs = validate(st_ruim)
        assert any("grupo_id" in e for e in errs), "validacao nao pegou grupo_id orfao"
        print("  [ok] validate detecta grupo_id orfao")

        # 6. migrate idempotente
        _, changed = migrate(load(wd))
        assert changed is False, "migrate deveria ser no-op em versao atual"
        print("  [ok] migrate no-op na versao atual")

    print("RESULTADO: state.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(main())
