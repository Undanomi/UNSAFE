from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from ..models import ScenarioDraft
from ..scenario_manifest import ManifestFlagPlacement, ScenarioManifest


def configured_flag_placements(
    manifest: ScenarioManifest,
    scenario: ScenarioDraft,
) -> list[tuple[ManifestFlagPlacement, str]]:
    values = {"user": scenario.user_flag, "system": scenario.system_flag}
    return [
        (placement, value)
        for placement in manifest.flag_placements
        if (value := values[placement.kind]) is not None
    ]


def render_flag_install_script(manifest: ScenarioManifest, scenario: ScenarioDraft) -> str:
    blocks: list[str] = []
    for placement, value in configured_flag_placements(manifest, scenario):
        path = shlex.quote(placement.path)
        parent = shlex.quote(str(PurePosixPath(placement.path).parent))
        owner = shlex.quote(placement.owner)
        group = shlex.quote(placement.group)
        blocks.append(
            f"test -d {parent}\n"
            f"getent passwd {owner} >/dev/null\n"
            f"getent group {group} >/dev/null\n"
            f"test ! -L {path}\n"
            f"printf '%s\\n' {shlex.quote(value)} | "
            f"install -o {owner} -g {group} -m {placement.mode} /dev/stdin {path}\n"
        )
    return "#!/bin/bash\nset -euo pipefail\numask 077\n\n" + "\n".join(blocks)


def flag_verification_commands(
    manifest: ScenarioManifest,
    scenario: ScenarioDraft,
) -> list[str]:
    commands: list[str] = []
    for placement, value in configured_flag_placements(manifest, scenario):
        path = shlex.quote(placement.path)
        identity = shlex.quote(
            f"{placement.mode.lstrip('0')}:{placement.owner}:{placement.group}:1"
        )
        commands.append(
            f"test -f {path} && test ! -L {path} && "
            f"test \"$(stat -c '%a:%U:%G:%h' -- {path})\" = {identity} && "
            f'test "$(cat -- {path})" = {shlex.quote(value)} && '
            f"runuser -u {shlex.quote(placement.owner)} -- test -r {path} && "
            f"runuser -u nobody -- test ! -r {path}"
        )
    return commands
