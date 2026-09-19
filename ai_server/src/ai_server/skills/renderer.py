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
            skill.verify_checksum()
            references = {item.reference_id: item for item in skill.references}
            details = []
            if skill.selection_reason.startswith("explicit"):
                details.append(
                    "このSkillは利用者が明示的に選択しています。今回の生成・検証に適用してください。"
                )
            for reference_id in skill.selected_reference_ids:
                reference = references[reference_id]
                details.append(
                    f'<reference id="{html.escape(reference_id)}" checksum="{reference.checksum}">\n'
                    f"{html.escape(reference.content)}\n</reference>"
                )
            if skill.name == "cve":
                if skill.reference_mode == "required" and skill.selected_reference_ids:
                    guidance = (
                        "明示指定された次のCVEはすべて使用してください。追加CVEの利用も可能です: "
                    )
                elif skill.reference_mode == "used":
                    guidance = "攻撃グラフで採用したCVEのうち、登録済みreferenceがあるもの: "
                else:
                    guidance = "参考となるCVE候補です。採用は任意で、候補以外のCVEも公式情報とOS適合性の検証を通過すれば利用できます: "
                details.insert(0, guidance + (", ".join(skill.selected_reference_ids) or "なし"))
            sections.append(
                f'<skill name="{html.escape(skill.name)}" version="{skill.version}">\n'
                f"{html.escape(skill.instructions)}\n" + "\n".join(details) + "\n"
                "</skill>"
            )
        return "<selected-skills>\n" + "\n\n".join(sections) + "\n</selected-skills>"
