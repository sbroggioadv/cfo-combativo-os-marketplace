#!/usr/bin/env python3
"""
resolve-state.py — Resolve qual cfo-state.json esta ativo.

Adaptado de calculosjudiciais/resolve-persona.py. Fallback chain
(ordem de prioridade):
  1. Env var CFO_STATE aponta para um cfo-state.json existente
  2. <CWD>/.claude/settings.local.json -> env.CFO_STATE
  3. ~/.config/cfo-combativo-os/active.json -> state_path
  4. Fallback: procura <CWD>/.cfo/cfo-state.json subindo ate 5 niveis

Imprime em stdout o PATH do state ativo + um diagnostico. Saida JSON
(stdout) para ser consumida por script; diagnostico humano em stderr.

LGPD (trava 3): este script NUNCA imprime o conteudo do state (que tem
docs mascarados e grafo financeiro) — so o caminho e a fonte.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

STATE_DIR = ".cfo"
STATE_FILENAME = "cfo-state.json"
ENV_VAR = "CFO_STATE"
CONFIG_DIRNAME = "cfo-combativo-os"


def _is_state_file(p: Path) -> bool:
    return p.exists() and p.is_file() and p.name == STATE_FILENAME


def _try_env_var() -> Path | None:
    p = os.environ.get(ENV_VAR)
    if p:
        path = Path(p).expanduser()
        if _is_state_file(path):
            return path
    return None


def _try_settings_local() -> Path | None:
    cwd = Path.cwd()
    for _ in range(5):
        settings = cwd / ".claude" / "settings.local.json"
        if settings.exists():
            try:
                data = json.loads(settings.read_text(encoding="utf-8"))
                env = data.get("env", {}) if isinstance(data, dict) else {}
                p = env.get(ENV_VAR)
                if p:
                    path = Path(p).expanduser()
                    if _is_state_file(path):
                        return path
            except (json.JSONDecodeError, PermissionError):
                pass
        if cwd.parent == cwd:
            break
        cwd = cwd.parent
    return None


def _try_active_config() -> Path | None:
    home = Path.home()
    for config_path in (
        home / ".config" / CONFIG_DIRNAME / "active.json",
        home / f".{CONFIG_DIRNAME}" / "active.json",
    ):
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                p = data.get("state_path")
                if p:
                    path = Path(p).expanduser()
                    if _is_state_file(path):
                        return path
            except (json.JSONDecodeError, PermissionError):
                pass
    return None


def _try_cwd_walk() -> Path | None:
    cwd = Path.cwd()
    for _ in range(6):
        cand = cwd / STATE_DIR / STATE_FILENAME
        if _is_state_file(cand):
            return cand
        if cwd.parent == cwd:
            break
        cwd = cwd.parent
    return None


def resolve_state() -> tuple[Path | None, str]:
    """Resolve o state ativo via fallback chain. Retorna (path|None, source_tag)."""
    for fn, tag in (
        (_try_env_var, f"env:{ENV_VAR}"),
        (_try_settings_local, "settings.local.json"),
        (_try_active_config, "active.json"),
        (_try_cwd_walk, "cwd-walk"),
    ):
        try:
            p = fn()
            if p:
                return p, tag
        except Exception:  # noqa: BLE001 — degradacao graciosa
            continue
    return None, "nenhum"


def main() -> int:
    path, source = resolve_state()
    if path is None:
        sys.stderr.write(
            "[cfo-combativo-os] Nenhum cfo-state.json encontrado. "
            "Rode /cfo-setup para montar o grafo de entidades.\n"
        )
        print(json.dumps({"resolved": False, "source": source, "path": None}, ensure_ascii=False))
        return 1

    sys.stderr.write(f"[cfo-combativo-os] State ativo via {source}: {path}\n")
    print(json.dumps(
        {"resolved": True, "source": source, "path": str(path)},
        ensure_ascii=False,
    ))
    return 0


# ---------------------------------------------------------------------------
# Auto-teste (dado SINTETICO)
# ---------------------------------------------------------------------------

def _auto_teste() -> int:
    import tempfile
    print("== AUTO-TESTE resolve-state.py (dado sintetico) ==")
    falhas = 0
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        cfo_dir = wd / STATE_DIR
        cfo_dir.mkdir(parents=True)
        sf = cfo_dir / STATE_FILENAME
        sf.write_text('{"schema_version":"1.0.0"}', encoding="utf-8")

        # 1. resolve por env var
        os.environ[ENV_VAR] = str(sf)
        p, src = resolve_state()
        assert p == sf and src.startswith("env:"), f"env resolution falhou: {p} {src}"
        print("  [ok] resolve via env var")
        del os.environ[ENV_VAR]

        # 2. env apontando para arquivo inexistente cai pro proximo
        os.environ[ENV_VAR] = str(wd / "nao-existe.json")
        old_cwd = os.getcwd()
        try:
            os.chdir(wd)
            p, src = resolve_state()
            # cwd-walk deve achar o state real
            assert p is not None and src == "cwd-walk", f"fallback cwd-walk falhou: {p} {src}"
            print("  [ok] env invalida -> fallback cwd-walk")
        finally:
            os.chdir(old_cwd)
            del os.environ[ENV_VAR]

    # 3. ausencia total nao quebra (degradacao graciosa)
    with tempfile.TemporaryDirectory() as td:
        old_cwd = os.getcwd()
        try:
            os.chdir(td)
            os.environ.pop(ENV_VAR, None)
            p, src = resolve_state()
            assert p is None and src == "nenhum", f"ausencia deveria retornar None: {p} {src}"
            print("  [ok] ausencia total -> (None, 'nenhum') sem excecao")
        finally:
            os.chdir(old_cwd)

    print("RESULTADO: resolve-state.py PASSOU" if falhas == 0 else f"RESULTADO: {falhas} FALHAS")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-teste":
        sys.exit(_auto_teste())
    sys.exit(main())
