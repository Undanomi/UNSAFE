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
    ScenarioReview,
    SourceFile,
    SourcePatch,
    SourceReview,
)
from ..prompts import (
    attack_graph_prompt,
    code_prompt,
    repair_prompt,
    scenario_prompt,
    scenario_review_prompt,
    source_review_prompt,
)

CVE_PATTERN = re.compile(r"^CVE-(\d{4})-\d{4,7}$")
GEMINI_JSON_SCHEMA_KEYS = {
    "$anchor",
    "$defs",
    "$id",
    "$ref",
    "additionalProperties",
    "anyOf",
    "description",
    "enum",
    "format",
    "items",
    "maximum",
    "minItems",
    "minimum",
    "oneOf",
    "prefixItems",
    "properties",
    "propertyOrdering",
    "required",
    "title",
    "type",
}


def _gemini_json_schema(value):
    if isinstance(value, list):
        return [_gemini_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    schema = {}
    for key, item in value.items():
        if key not in GEMINI_JSON_SCHEMA_KEYS:
            continue
        if key in {"$defs", "properties"}:
            schema[key] = {name: _gemini_json_schema(child) for name, child in item.items()}
        else:
            schema[key] = _gemini_json_schema(item)
    return schema


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

    async def review_scenario(
        self, machine: MachineInformation, scenario: ScenarioDraft
    ) -> ScenarioReview: ...

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

    async def review_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
    ) -> SourceReview: ...


class GeminiGenerator:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    async def _generate(
        self,
        prompt: str,
        *,
        json_output: bool = False,
        response_schema: type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        if not self.settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        generation_config: dict[str, object] = {}
        if json_output or response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
        if response_schema is not None:
            generation_config["responseJsonSchema"] = _gemini_json_schema(
                response_schema.model_json_schema()
            )
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
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            detail = response.text.strip()[:2000]
            message = f"{error}; Gemini response: {detail}" if detail else str(error)
            raise httpx.HTTPStatusError(
                message,
                request=error.request,
                response=error.response,
            ) from error
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
            response_schema=AttackGraph,
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

    async def _debian_evidence(self, cve_id: str, target_os: str) -> dict | None:
        match = re.fullmatch(
            r"debian\s+(\d+)(?:\.\d+){0,2}", target_os.strip(), re.IGNORECASE
        )
        if not match:
            return None
        ecosystem = f"Debian:{match.group(1)}"
        response = await self.client.get(f"https://api.osv.dev/v1/vulns/DEBIAN-{cve_id}")
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
    def _compact_record(cve_id: str, record: dict, debian: dict | None, refs: list[str]) -> dict:
        cna = record.get("containers", {}).get("cna", {})
        return {
            "cve_id": cve_id,
            "descriptions": cna.get("descriptions", [])[:3],
            "affected": cna.get("affected", [])[:20],
            "references": [item.get("url") for item in cna.get("references", [])[:20]],
            "debian_osv": debian,
            "public_poc_repositories": refs,
            "official_cve_url": f"https://www.cve.org/CVERecord?id={cve_id}",
        }

    async def _verify_cve_step(self, machine: MachineInformation, step: AttackStep) -> AttackStep:
        assert step.cve_id is not None
        self._validate_cve_id(step.cve_id)
        record, debian, github_refs = await asyncio.gather(
            self._cve_record(step.cve_id),
            self._debian_evidence(step.cve_id, machine.operating_system),
            self._github_references(step.cve_id),
        )
        evidence = self._compact_record(step.cve_id, record, debian, github_refs)
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
- OSまたはカーネルのCVEは、Debian OSVに対象リリースのaffectedがなければos_compatible=false
- アプリケーションCVEは、対象OS上で脆弱版を固定導入できる場合だけos_compatible=true
- referencesは証拠に含まれるURLだけを使用する
"""
        verification = CVEVerification.model_validate_json(
            await self._generate(
                prompt,
                json_output=True,
                response_schema=CVEVerification,
            )
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
        debian = evidence.get("debian_osv")
        if "linux kernel" in record_text and debian is not None and not debian["affected"]:
            verification.os_compatible = False
            verification.compatibility_reason = (
                f"{debian['ecosystem']} has no affected entry in Debian OSV"
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
                scenario = ScenarioDraft(
                    scenario_id=f"scenario-{uuid4().hex}",
                    title=machine.name,
                    definition=definition,
                    target_os=machine.operating_system,
                    attack_graph=graph,
                )
                review = await self.review_scenario(machine, scenario)
                if review.approved:
                    return scenario
                review_report = _compact_scenario_review(review)
                last_error = ValueError(f"scenario semantic review failed: {review.summary}")
                rejected.append(
                    "scenario_semantic_review: " + json.dumps(review_report, ensure_ascii=False)
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
        raise RuntimeError(f"Could not generate an approved scenario: {last_error}")

    async def review_scenario(
        self, machine: MachineInformation, scenario: ScenarioDraft
    ) -> ScenarioReview:
        last_error: Exception | None = None
        prompt = scenario_review_prompt(machine, scenario)
        for _ in range(self.settings.generation_retries):
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=ScenarioReview,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                return ScenarioReview.model_validate_json(response)
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error)
        raise RuntimeError(f"Could not review scenario: {last_error}")

    async def generate_source(
        self, machine: MachineInformation, scenario: ScenarioDraft
    ) -> GeneratedSource:
        last_error: Exception | None = None
        prompt = code_prompt(machine, scenario)
        for _ in range(self.settings.generation_retries):
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=GeneratedSource,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                generated = GeneratedSource.model_validate_json(response)
                _validate_generated_file_payload(generated.files)
                return generated
            except (httpx.HTTPError, RuntimeError, TypeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error)
        raise RuntimeError(f"Could not generate valid VM source: {last_error}")

    async def repair_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        failure_report: dict,
    ) -> SourcePatch:
        last_error: Exception | None = None
        retry_report = failure_report
        for _ in range(self.settings.generation_retries):
            try:
                response = await self._generate(
                    repair_prompt(machine, scenario, current, retry_report),
                    json_output=True,
                    response_schema=SourcePatch,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                patch = SourcePatch.model_validate_json(response)
                _validate_generated_file_payload(patch.files)
                return patch
            except (httpx.HTTPError, RuntimeError, TypeError, ValueError) as error:
                last_error = error
                retry_report = {
                    **failure_report,
                    "model_output_validation_error": str(error),
                }
        raise RuntimeError(f"Could not repair VM source: {last_error}")

    async def review_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
    ) -> SourceReview:
        last_error: Exception | None = None
        prompt = source_review_prompt(machine, scenario, current)
        for _ in range(self.settings.generation_retries):
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=SourceReview,
                    max_output_tokens=self.settings.gemini_max_output_tokens,
                )
                return SourceReview.model_validate_json(response)
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error)
        raise RuntimeError(f"Could not review VM source: {last_error}")


def _validate_generated_file_payload(files: list[SourceFile]) -> None:
    paths: set[str] = set()
    for source_file in files:
        if source_file.path in paths:
            raise ValueError(f"duplicate generated path: {source_file.path}")
        paths.add(source_file.path)
        if source_file.path != "contents/scenario_manifest.json":
            continue
        try:
            manifest = json.loads(source_file.content)
        except json.JSONDecodeError as error:
            raise ValueError(f"scenario_manifest.json is not valid JSON: {error}") from error
        if not isinstance(manifest, dict):
            raise TypeError("scenario_manifest.json root must be a JSON object")


def _prompt_with_rejection(prompt: str, error: Exception) -> str:
    return (
        prompt
        + "\n\n前回の出力は次の理由で受理できませんでした。同じ誤りを繰り返さず、"
        + "全体を正しいJSONとして再生成してください:\n"
        + str(error)[:2_000]
    )


def _compact_scenario_review(review: ScenarioReview) -> dict:
    findings = []
    for finding in review.findings[:8]:
        findings.append(
            {
                "step_id": finding.step_id,
                "severity": finding.severity,
                "category": finding.category,
                "evidence": finding.evidence[:500],
                "remediation": finding.remediation[:500],
            }
        )
    return {
        "summary": review.summary[:1_000],
        "findings": findings,
        "omitted_findings": max(0, len(review.findings) - len(findings)),
    }
