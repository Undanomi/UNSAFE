from __future__ import annotations

import asyncio
import json
import re
from typing import Protocol
from uuid import uuid4

import httpx
from pydantic import ValidationError

from ..config import Settings
from ..models import (
    CVEInstallationPlan,
    GeneratedSource,
    MachineInformation,
    ScenarioDraft,
    SourcePatch,
)
from ..prompts import code_prompt, repair_prompt, scenario_prompt

CVE_PATTERN = re.compile(r"^CVE-(\d{4})-\d{4,7}$")


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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
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
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return text

    async def _select_cves(
        self, machine: MachineInformation, rejected: list[str]
    ) -> tuple[str, str]:
        rejection_context = "\n".join(rejected[-5:]) or "なし"
        prompt = f"""テーマ「{machine.theme}」、難易度「{machine.difficulty}」、対象OS
「{machine.operating_system}」の教育用マシンで実際に導入・再現できるCVEを2件選んでください。
実在するCVEを2件選んでください。initial_cveは認証前の初期侵入、privesc_cveは一般ユーザーからrootへの権限昇格です。
どちらも{self.settings.cve_min_year}年以降に公開されたCVEに限定してください。
対象OSでは脆弱にならないカーネルCVEや、脆弱版を導入できないソフトウェアを選ばないでください。
これまで棄却された候補と理由は次の通りです。同じCVEを選ばないでください:
{rejection_context}
JSONのみを返してください: {{"initial_cve":"CVE-YYYY-NNNN","privesc_cve":"CVE-YYYY-NNNN"}}"""
        data = json.loads(await self._generate(prompt, json_output=True))
        initial, privesc = data["initial_cve"], data["privesc_cve"]
        for cve_id in (initial, privesc):
            match = CVE_PATTERN.fullmatch(cve_id)
            if not match:
                raise ValueError("Gemini selected an invalid CVE identifier")
            if int(match.group(1)) < self.settings.cve_min_year:
                raise ValueError(
                    f"{cve_id} is older than minimum year {self.settings.cve_min_year}"
                )
        return initial, privesc

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

    async def _installation_plans(
        self,
        machine: MachineInformation,
        initial: dict,
        privesc: dict,
    ) -> list[CVEInstallationPlan]:
        evidence = [initial, privesc]
        prompt = f"""次の公式CVEレコードとUbuntu OSV情報を根拠に、対象OSで脆弱性を
実際に導入できるか検証してください。推測でcompatibleにしないでください。

対象OS: {machine.operating_system}
証拠:
{json.dumps(evidence, ensure_ascii=False)}

JSONのみを返してください:
{{"plans":[{{"cve_id":"CVE-...","role":"initial_access","software":"...",
"vulnerable_version":"...","os_compatible":true,"compatibility_reason":"...",
"installation_method":"...","installation_steps":["..."],"references":["..."]}},
{{"cve_id":"CVE-...","role":"privilege_escalation",...}}]}}

条件:
- {initial["cve_id"]} のroleはinitial_access
- {privesc["cve_id"]} のroleはprivilege_escalation
- OSまたはカーネル自体のCVEは、Ubuntu OSVに対象リリースのaffectedエントリがなければfalse
- アプリケーションCVEは対象OS上で脆弱版を固定して導入できる具体的方法がある場合だけtrue
- installation_stepsには脆弱版の取得、固定、設定、起動確認を具体的に含める
- referencesは証拠内のURLだけを使う
"""
        response = await self._generate(prompt, json_output=True)
        value = json.loads(response)
        raw_plans = value.get("plans") if isinstance(value, dict) else value
        if not isinstance(raw_plans, list):
            raise TypeError("CVE installation response must contain a plans array")
        expected = {
            initial["cve_id"]: "initial_access",
            privesc["cve_id"]: "privilege_escalation",
        }
        if len(raw_plans) != 2 or not all(isinstance(item, dict) for item in raw_plans):
            raise ValueError("CVE installation response must contain two plan objects")
        plans_by_id = {item.get("cve_id"): item for item in raw_plans}
        if len(plans_by_id) != 2 or set(plans_by_id) != set(expected):
            raise ValueError(
                f"CVE installation plan identifiers do not match: "
                f"expected={list(expected)}, actual={list(plans_by_id)}"
            )
        plans = []
        for cve_id, role in expected.items():
            normalized = {**plans_by_id[cve_id], "role": role}
            plans.append(CVEInstallationPlan.model_validate(normalized))
        self._enforce_kernel_evidence(plans, evidence)
        if not all(plan.os_compatible for plan in plans):
            rejected = [
                f"{plan.cve_id}: {plan.compatibility_reason}"
                for plan in plans
                if not plan.os_compatible
            ]
            raise ValueError(f"CVE is not compatible with target OS: {rejected}")
        return plans

    @staticmethod
    def _enforce_kernel_evidence(plans: list[CVEInstallationPlan], evidence: list[dict]) -> None:
        for plan, item in zip(plans, evidence, strict=True):
            record_text = json.dumps(
                [item.get("descriptions", []), item.get("affected", [])]
            ).lower()
            ubuntu = item.get("ubuntu_osv")
            if "linux kernel" in record_text and ubuntu is not None and not ubuntu["affected"]:
                plan.os_compatible = False
                plan.compatibility_reason = (
                    f"{ubuntu['ecosystem']} has no affected entry in Ubuntu OSV"
                )

    async def generate_scenario(self, machine: MachineInformation) -> ScenarioDraft:
        last_error: Exception | None = None
        rejected: list[str] = []
        for _ in range(self.settings.cve_selection_attempts):
            try:
                initial, privesc = await self._select_cves(machine, rejected)
                (
                    initial_record,
                    privesc_record,
                    initial_osv,
                    privesc_osv,
                    initial_refs,
                    privesc_refs,
                ) = await asyncio.gather(
                    self._cve_record(initial),
                    self._cve_record(privesc),
                    self._ubuntu_evidence(initial, machine.operating_system),
                    self._ubuntu_evidence(privesc, machine.operating_system),
                    self._github_references(initial),
                    self._github_references(privesc),
                )
                initial_evidence = self._compact_record(
                    initial, initial_record, initial_osv, initial_refs
                )
                privesc_evidence = self._compact_record(
                    privesc, privesc_record, privesc_osv, privesc_refs
                )
                plans = await self._installation_plans(machine, initial_evidence, privesc_evidence)
                context = "検証済みCVE証拠と導入計画:\n" + json.dumps(
                    {
                        "target_os": machine.operating_system,
                        "evidence": [initial_evidence, privesc_evidence],
                        "installation_plans": [plan.model_dump(mode="json") for plan in plans],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                definition = await self._generate(scenario_prompt(machine, context))
                return ScenarioDraft(
                    scenario_id=f"scenario-{uuid4().hex}",
                    title=machine.name,
                    definition=definition,
                    target_os=machine.operating_system,
                    initial_cve=initial,
                    privilege_escalation_cve=privesc,
                    cve_installation=plans,
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
        raise RuntimeError(f"Could not generate a verified scenario: {last_error}")

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
