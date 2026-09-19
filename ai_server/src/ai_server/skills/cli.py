from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .loader import SkillDefinition, load_skills


async def _publish(definitions: list[SkillDefinition]) -> None:
    from ..config import Settings
    from ..repository import SessionRepository
    from .repository import SkillRepository

    settings = Settings()
    repository = SessionRepository(settings.database_url)
    try:
        await repository.initialize()
        results = await SkillRepository(repository.session_factory).publish_definitions(
            [(item.metadata, item.version) for item in definitions]
        )
        for skill, changed in results:
            print(
                f"{'published' if changed else 'unchanged'}: {skill.name}@{skill.version} checksum={skill.content_checksum}"
            )
    finally:
        await repository.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and publish Skill definitions")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "publish"):
        command = commands.add_parser(name)
        command.add_argument("path", type=Path, help="Definition root or a single Skill directory")
        if name == "publish":
            command.add_argument("--created-by", required=True)
    args = parser.parse_args(argv)
    try:
        definitions = load_skills(args.path, created_by=getattr(args, "created_by", "validation"))
        if args.command == "validate":
            for item in definitions:
                print(
                    f"valid: {item.metadata.name} body_chars={len(item.version.instructions)} references={len(item.version.references)}"
                )
        else:
            asyncio.run(_publish(definitions))
        return 0
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
