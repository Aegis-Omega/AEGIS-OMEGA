#!/usr/bin/env python3
"""Check, optionally register, and truthfully report a Codex/Circle MCP binding.

Python >=3.11; stdlib only. Never reads, prints, or persists authentication tokens.
No network probes. Registration is explicit, scoped to an operator-supplied CODEX_HOME.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

CIRCLE_URL = 'https://api.circle.com/v1/codegen/mcp'
SCHEMA = 'aegis.circle-mcp-preflight.v1'


def inspect_config(home: Path) -> dict[str, str]:
    path = home / 'config.toml'
    if not path.exists() and not path.is_symlink():
        return {'status': 'NOT_CONFIGURED'}
    if home.is_symlink() or path.is_symlink():
        return {'status': 'UNSAFE_CONFIG_PATH'}
    try:
        with path.open('rb') as stream:
            obj = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return {'status': 'UNREADABLE_CONFIG'}
    server_table = obj.get('mcp_servers')
    if not isinstance(server_table, dict) or 'circle' not in server_table:
        return {'status': 'NOT_CONFIGURED'}
    server = server_table['circle']
    if not isinstance(server, dict) or server.get('url') != CIRCLE_URL:
        return {'status': 'MISMATCH_OR_UNSUPPORTED'}
    if server.get('enabled', True) is not True:
        return {'status': 'DISABLED'}
    return {'status': 'CONFIGURED_ONLY', 'transport': 'streamable_http'}


def cli_version(binary: str | None) -> dict[str, str]:
    if not binary:
        return {'status': 'NOT_FOUND'}
    try:
        result = subprocess.run([binary, '--version'], capture_output=True, text=True,
                                check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'UNVERIFIED'}
    if result.returncode != 0 or not result.stdout.startswith('codex '):
        return {'status': 'UNVERIFIED'}
    # We do not print subprocess stderr, which could contain sensitive information.
    return {'status': 'VERSION_CONFIRMED', 'version': result.stdout.strip()[:96]}


def register(home: Path, binary: str | None) -> str:
    """Explicit write; no overwrites, no automatic authentication or payment."""
    if home.is_symlink() or (home / 'config.toml').is_symlink():
        return 'DENIED_UNSAFE_PATH'
    existing = inspect_config(home)
    if existing['status'] == 'CONFIGURED_ONLY':
        return 'ALREADY_REGISTERED'
    if existing['status'] != 'NOT_CONFIGURED':
        return 'DENIED_EXISTING_CONFIG'
    if not binary or cli_version(binary)['status'] != 'VERSION_CONFIRMED':
        return 'NO_VERIFIED_CODEX'
    try:
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Reject a directory replaced by a symlink during preflight.
        if home.is_symlink() or not home.is_dir():
            return 'DENIED_UNSAFE_PATH'
        result = subprocess.run([binary, 'mcp', 'add', 'circle', '--url', CIRCLE_URL],
                                env={**os.environ, 'CODEX_HOME': str(home)},
                                capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 'REGISTRATION_NOT_VERIFIED'
    if result.returncode != 0:
        return 'REGISTRATION_NOT_VERIFIED'
    if inspect_config(home)['status'] != 'CONFIGURED_ONLY':
        return 'REGISTRATION_NOT_VERIFIED'
    return 'REGISTERED_CONFIG_ONLY'


def inspect(home: Path, binary: str | None, registration: str = 'NOT_REQUESTED') -> dict:
    return {
        'schema': SCHEMA,
        'target': 'Codex CLI (operator-supplied profile)',
        'server': 'circle',
        'url': CIRCLE_URL,
        'cli': cli_version(binary),
        'registration': registration,
        'config': inspect_config(home),
        'live_transport': 'NOT_TESTED',
        'remote_tools': 'NOT_TESTED',
        'auth': 'NOT_TESTED',
        'authority_granted': False,
        'production_write': 'NOT_PERFORMED',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, help='Dedicated Codex profile directory')
    parser.add_argument('--codex', help='Path to Codex executable (else PATH)')
    parser.add_argument('--register', action='store_true', help='Explicitly register Circle in --codex-home')
    ns = parser.parse_args(argv)
    if ns.register and ns.codex_home is None:
        parser.error('--register requires explicit --codex-home; default user profile is never modified')
    home = (ns.codex_home or Path(os.environ.get('CODEX_HOME', '~/.codex'))).expanduser().absolute()
    binary = ns.codex or shutil.which('codex')
    outcome = register(home, binary) if ns.register else 'NOT_REQUESTED'
    report = inspect(home, binary, outcome)
    print(json.dumps(report, sort_keys=True, indent=2))
    success = report['cli']['status'] == 'VERSION_CONFIRMED' and report['config']['status'] == 'CONFIGURED_ONLY'
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
