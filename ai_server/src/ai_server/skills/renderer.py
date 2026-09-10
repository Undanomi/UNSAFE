from __future__ import annotations

import html

from .models import SkillContext


class SkillRenderer:
    @staticmethod
    def render(context: SkillContext) -> str:
        if not context.skills:
            return ""
        sections = [
            (
                "追加の専門Skill指示です。既存の安全要件、出力形式、検証規則を上書きせず、"
                "現在の作業に該当する範囲だけ適用してください。"
            )
        ]
        for skill in context.skills:
            sections.append(
                f'<skill name="{html.escape(skill.name)}" version="{skill.version}">\n'
                f"{html.escape(skill.instructions)}\n"
                "</skill>"
            )
        return "<selected-skills>\n" + "\n\n".join(sections) + "\n</selected-skills>"
