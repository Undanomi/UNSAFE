from __future__ import annotations

import asyncio
import json
import re
from typing import Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from ..config import Settings
from ..models import (
    AttackGraph,
    AttackObjective,
    AttackStep,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
    SourcePatch,
)
from ..prompts import attack_graph_prompt, code_prompt, repair_prompt, scenario_prompt

CVE_PATTERN = re.compile(r"^CVE-(\d{4})-\d{4,7}$")


class CVEVerification(BaseModel):
    software: str = Field(min_length=1, max_length=200)
    vulnerable_version: str = Field(min_length=1, max_length=200)
    os_compatible: bool
    compatibility_reason: str = Field(min_length=1, max_length=2000)
    installation_method: str | None = Field(default=None, max_length=500)
    implementation_steps: list[str] = Field(default_factory=list, max_length=50)
    references: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def require_implementation_for_compatible_cve(self) -> CVEVerification:
        if self.os_compatible and (not self.installation_method or not self.implementation_steps):
            raise ValueError("compatible CVE requires an installation method and steps")
        return self


class AIGenerator(Protocol):
    async def generate_scenario(self, machine: MachineInformation) -> ScenarioDraft: ...

    async def generate_source(
        self, machine: MachineInformation, scenario: ScenarioDraft
    ) -> GeneratedSource: ...

    async def repair_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        failure_report: dict,
    ) -> SourcePatch: ...


class GeminiGenerator:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    async def _generate(
        self,
        prompt: str,
        *,
        json_output: bool = False,
        max_output_tokens: int | None = None,
    ) -> str:
        if not self.settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        generation_config = {"responseMimeType": "application/json"} if json_output else {}
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        response = await self.client.post(
            url,
            headers={"x-goog-api-key": self.settings.gemini_api_key or ""},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            },
        )
        response.raise_for_status()
        candidates = response.json().get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        finish_reason = candidates[0].get("finishReason")
        if finish_reason and finish_reason != "STOP":
            raise RuntimeError(f"Gemini generation stopped with {finish_reason}")
        parts = candidates[0].get("content", {}).get("parts", [])
        generated_text = "".join(part.get("text", "") for part in parts).strip()
        if not generated_text:
            raise RuntimeError("Gemini returned an empty response")
        return generated_text

    async def _draft_attack_graph(
        self, machine: MachineInformation, rejected: list[str]
    ) -> AttackGraph:
        response = await self._generate(
            attack_graph_prompt(machine, rejected, self.settings.cve_min_year),
            json_output=True,
            max_output_tokens=self.settings.gemini_max_output_tokens,
        )
        value = json.loads(response)
        raw_graph = value.get("attack_graph", value) if isinstance(value, dict) else value
        graph = AttackGraph.model_validate(raw_graph)
        self._validate_objectives(machine, graph)
        for step in graph.steps:
            if step.kind == "cve":
                self._validate_cve_id(step.cve_id or "")
        return AttackGraph(objectives=self._expected_objectives(machine), steps=graph.steps)

    @staticmethod
    def _expected_objectives(machine: MachineInformation) -> list[AttackObjective]:
        objectives = []
        if machine.needs_user_flag:
            objectives.append(
                AttackObjective(
                    objective_id="user-flag",
                    objective_type="user_flag",
                    description=machine.user_flag_details,
                )
            )
        if machine.needs_system_flag:
            objectives.append(
                AttackObjective(
                    objective_id="system-flag",
                    objective_type="system_flag",
                    description=machine.system_flag_details,
                )
            )
        return objectives

    @classmethod
    def _validate_objectives(cls, machine: MachineInformation, graph: AttackGraph) -> None:
        expected = {
            (objective.objective_id, objective.objective_type)
            for objective in cls._expected_objectives(machine)
        }
        actual = {
            (objective.objective_id, objective.objective_type) for objective in graph.objectives
        }
        if actual != expected:
            raise ValueError(
                f"attack graph objectives do not match machine flags: "
                f"expected={sorted(expected)}, actual={sorted(actual)}"
            )

    def _validate_cve_id(self, cve_id: str) -> None:
        match = CVE_PATTERN.fullmatch(cve_id)
        if not match:
            raise ValueError(f"invalid CVE identifier: {cve_id}")
        if int(match.group(1)) < self.settings.cve_min_year:
            raise ValueError(f"{cve_id} is older than minimum year {self.settings.cve_min_year}")

    async def _cve_record(self, cve_id: str) -> dict:
        response = await self.client.get(f"https://cveawg.mitre.org/api/cve/{cve_id}")
        response.raise_for_status()
        return response.json()

    async def _ubuntu_evidence(self, cve_id: str, target_os: str) -> dict | None:
        match = re.search(r"ubuntu\s+(\d+\.\d+)", target_os, re.IGNORECASE)
        if not match:
            return None
        ecosystem = f"Ubuntu:{match.group(1)}:LTS"
        response = await self.client.get(f"https://api.osv.dev/v1/vulns/UBUNTU-{cve_id}")
        if response.status_code == 404:
            return {"ecosystem": ecosystem, "tracked": False, "affected": []}
        response.raise_for_status()
        affected = [
            item
            for item in response.json().get("affected", [])
            if item.get("package", {}).get("ecosystem") == ecosystem
        ]
        return {"ecosystem": ecosystem, "tracked": True, "affected": affected}

    async def _github_references(self, cve_id: str) -> list[str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "slsg-ai-server"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        response = await self.client.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params={"q": cve_id, "sort": "stars", "order": "desc", "per_page": 5},
        )
        response.raise_for_status()
        return [
            item["html_url"] for item in response.json().get("items", []) if item.get("html_url")
        ]

    @staticmethod
    def _compact_record(cve_id: str, record: dict, ubuntu: dict | None, refs: list[str]) -> dict:
        cna = record.get("containers", {}).get("cna", {})
        return {
            "cve_id": cve_id,
            "descriptions": cna.get("descriptions", [])[:3],
            "affected": cna.get("affected", [])[:20],
            "references": [item.get("url") for item in cna.get("references", [])[:20]],
            "ubuntu_osv": ubuntu,
            "public_poc_repositories": refs,
            "official_cve_url": f"https://www.cve.org/CVERecord?id={cve_id}",
        }

    async def _verify_cve_step(self, machine: MachineInformation, step: AttackStep) -> AttackStep:
        assert step.cve_id is not None
        self._validate_cve_id(step.cve_id)
        record, ubuntu, github_refs = await asyncio.gather(
            self._cve_record(step.cve_id),
            self._ubuntu_evidence(step.cve_id, machine.operating_system),
            self._github_references(step.cve_id),
        )
        evidence = self._compact_record(step.cve_id, record, ubuntu, github_refs)
        prompt = f"""次の攻撃グラフ内のCVEステップを、公式CVEレコードと対象OSの証拠に基づいて
検証し、隔離された教育VMへ脆弱な状態を構築する計画をJSONで返してください。

対象OS: {machine.operating_system}
攻撃ステップ:
{step.model_dump_json(indent=2)}
証拠:
{json.dumps(evidence, ensure_ascii=False)}

JSONのみを返してください:
{{"software":"...","vulnerable_version":"...","os_compatible":true,
"compatibility_reason":"...","installation_method":"...",
"implementation_steps":["取得","固定","設定","起動確認"],"references":["..."]}}

規則:
- OSまたはカーネルのCVEは、Ubuntu OSVに対象リリースのaffectedがなければos_compatible=false
- アプリケーションCVEは、対象OS上で脆弱版を固定導入できる場合だけos_compatible=true
- referencesは証拠に含まれるURLだけを使用する
"""
        verification = CVEVerification.model_validate_json(
            await self._generate(prompt, json_output=True)
        )
        self._enforce_kernel_evidence(verification, evidence)
        if not verification.os_compatible:
            raise ValueError(
                f"{step.cve_id} is not compatible with {machine.operating_system}: "
                f"{verification.compatibility_reason}"
            )
        values = step.model_dump(mode="json")
        values.update(verification.model_dump(mode="json"))
        return AttackStep.model_validate(values)

    @staticmethod
    def _enforce_kernel_evidence(verification: CVEVerification, evidence: dict) -> None:
        record_text = json.dumps(
            [evidence.get("descriptions", []), evidence.get("affected", [])]
        ).lower()
        ubuntu = evidence.get("ubuntu_osv")
        if "linux kernel" in record_text and ubuntu is not None and not ubuntu["affected"]:
            verification.os_compatible = False
            verification.compatibility_reason = (
                f"{ubuntu['ecosystem']} has no affected entry in Ubuntu OSV"
            )

    async def _verify_attack_graph(
        self, machine: MachineInformation, graph: AttackGraph
    ) -> AttackGraph:
        cve_steps = [step for step in graph.steps if step.kind == "cve"]
        if not cve_steps:
            return AttackGraph(
                objectives=self._expected_objectives(machine),
                steps=graph.steps,
            )
        verified_steps = await asyncio.gather(
            *(self._verify_cve_step(machine, step) for step in cve_steps)
        )
        verified_by_id = {step.step_id: step for step in verified_steps}
        return AttackGraph(
            objectives=self._expected_objectives(machine),
            steps=[verified_by_id.get(step.step_id, step) for step in graph.steps],
        )

    async def generate_scenario(self, machine: MachineInformation) -> ScenarioDraft:
        last_error: Exception | None = None
        rejected: list[str] = []
        for _ in range(self.settings.scenario_generation_attempts):
            try:
                graph = await self._draft_attack_graph(machine, rejected)
                graph = await self._verify_attack_graph(machine, graph)
                definition = await self._generate(
                    scenario_prompt(machine, graph.model_dump_json(indent=2)),
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                return ScenarioDraft(
                    scenario_id=f"scenario-{uuid4().hex}",
                    title=machine.name,
                    definition=definition,
                    target_os=machine.operating_system,
                    attack_graph=graph,
                )
            except (
                httpx.HTTPError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                last_error = error
                rejected.append(str(error))
        raise RuntimeError(f"Could not generate a verified attack graph: {last_error}")

    async def generate_source(
        self, machine: MachineInformation, scenario: ScenarioDraft
    ) -> GeneratedSource:
        last_error: Exception | None = None
        for _ in range(self.settings.generation_retries):
            try:
                response = await self._generate(
                    code_prompt(machine, scenario),
                    json_output=True,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                return GeneratedSource.model_validate_json(response)
            except (httpx.HTTPError, RuntimeError, ValidationError) as error:
                last_error = error
        raise RuntimeError(f"Could not generate valid VM source: {last_error}")

    async def repair_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        failure_report: dict,
    ) -> SourcePatch:
        last_error: Exception | None = None
        for _ in range(self.settings.generation_retries):
            try:
                response = await self._generate(
                    repair_prompt(machine, scenario, current, failure_report),
                    json_output=True,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                return SourcePatch.model_validate_json(response)
            except (httpx.HTTPError, RuntimeError, ValidationError) as error:
                last_error = error
        raise RuntimeError(f"Could not repair VM source: {last_error}")
