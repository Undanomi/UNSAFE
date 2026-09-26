from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Literal, Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from ..config import Settings
from ..models import (
    SCENARIO_DEFINITION_MAX_CHARS,
    AttackGraph,
    AttackObjective,
    AttackStep,
    AutomaticFlagPlan,
    GeneratedSource,
    GuidancePlan,
    MachineInformation,
    ScenarioCorrection,
    ScenarioDraft,
    ScenarioGeneration,
    ScenarioReview,
    ScenarioRevision,
    ScenarioTextRevision,
    SourceFile,
    SourcePatch,
    SourceReview,
    SourceWorkbenchDecision,
)
from ..prompts import (
    attack_graph_json_for_ai,
    attack_graph_prompt,
    attack_graph_revision_prompt,
    automatic_flag_plan_prompt,
    code_prompt,
    guidance_prompt,
    repair_prompt,
    scenario_compaction_prompt,
    scenario_correction_prompt,
    scenario_prompt,
    scenario_review_prompt,
    scenario_sync_prompt,
    source_review_prompt,
    source_workbench_prompt,
)
from ..skills.models import ScenarioSkillContexts, SkillContext, SkillPhase
from ..skills.planning import context_for_graph
from ..skills.renderer import SkillRenderer
from ..skills.selector import SkillSelector
from .errors import ScenarioInputRevisionRequiredError

logger = logging.getLogger(__name__)
_TOKEN_USAGE_SESSION_ID: ContextVar[str | None] = ContextVar(
    "ai_token_usage_session_id", default=None
)
TokenUsageRecorder = Callable[[str, int, int, int], Awaitable[None]]


def begin_token_usage_session(session_id: str) -> Token:
    return _TOKEN_USAGE_SESSION_ID.set(session_id)


def end_token_usage_session(token: Token) -> None:
    _TOKEN_USAGE_SESSION_ID.reset(token)


CVE_PATTERN = re.compile(r"^CVE-(\d{4})-\d{4,7}$")
SCENARIO_DEFINITION_TARGET_CHARS = 10_500
ATTACK_GRAPH_REVISION_FIELDS = frozenset({"title", "description", "implementation_steps"})
MAX_REVIEW_RECONSIDERATIONS = 2
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


class _GeneratedArtifactValidationFailure(ValueError):
    """A generated artifact repeatedly failed deterministic validation."""

    def __init__(self, artifact_kind: str, error: Exception, attempted_output) -> None:
        self.artifact_kind = artifact_kind
        self.validation_error = str(error)
        try:
            serialized = json.dumps(attempted_output, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            serialized = repr(attempted_output)
        self.attempted_output = serialized[:12_000]
        super().__init__(f"{artifact_kind} validation failed: {error}")


class _ReviewReconsiderationExhausted(RuntimeError):
    """The reviewer repeated a repair request that cannot pass validation."""


class AIProviderRequestError(Exception):
    """A provider request cannot be completed within the bounded transport policy."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retryable = retryable


class AIProviderSafetyRefusalError(Exception):
    """The provider refused a request for a safety or policy reason."""

    def __init__(self, provider: str, detail: object) -> None:
        reason = str(detail).strip()[:2000] or "reason was not provided"
        self.summary = f"{provider} が安全ポリシー上の理由で処理を拒否しました: {reason}"
        super().__init__(self.summary)


class _SharedAIRequestGate:
    """Pace all requests made by one application-wide provider client."""

    def __init__(self, max_concurrent: int, min_interval_seconds: float) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._pacing_lock = asyncio.Lock()
        self._min_interval_seconds = min_interval_seconds
        self._next_start = 0.0

    async def request(
        self,
        operation: Callable[[], Awaitable[httpx.Response]],
        *,
        cooldown_for_response: Callable[[httpx.Response], float | None] | None = None,
        transport_cooldown_seconds: float = 0,
    ) -> httpx.Response:
        async with self._semaphore:
            async with self._pacing_lock:
                loop = asyncio.get_running_loop()
                delay = self._next_start - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                started = loop.time()
                self._next_start = max(self._next_start, started) + self._min_interval_seconds
            try:
                response = await operation()
            except httpx.TransportError:
                if transport_cooldown_seconds > 0:
                    await self.defer(transport_cooldown_seconds)
                raise
            if cooldown_for_response is not None:
                cooldown = cooldown_for_response(response)
                if cooldown is not None and cooldown > 0:
                    await self.defer(cooldown)
            return response

    async def defer(self, delay_seconds: float) -> None:
        async with self._pacing_lock:
            loop = asyncio.get_running_loop()
            self._next_start = max(self._next_start, loop.time() + delay_seconds)


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


def _openai_json_schema(value):
    """Convert Pydantic's schema to the strict subset accepted by Responses."""
    if isinstance(value, list):
        return [_openai_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    schema = {key: _openai_json_schema(item) for key, item in value.items() if key != "default"}
    properties = schema.get("properties")
    if schema.get("type") == "object" and isinstance(properties, dict):
        schema["required"] = list(properties)
        schema["additionalProperties"] = False
    return schema


async def _record_scenario_draft(
    observer: Callable[[], Awaitable[None]] | None,
    scenario: ScenarioDraft,
    review: ScenarioReview | None = None,
) -> None:
    if observer is None:
        return
    recorder = getattr(observer, "record_draft", None)
    if callable(recorder):
        await recorder(scenario, review)


async def _record_attack_graph(
    observer: Callable[[], Awaitable[None]] | None,
    graph: AttackGraph,
) -> None:
    if observer is None:
        return
    recorder = getattr(observer, "record_attack_graph", None)
    if callable(recorder):
        await recorder(graph)


async def _record_scenario_failure(
    observer: Callable[[], Awaitable[None]] | None,
    phase: str,
    error: Exception,
) -> None:
    if observer is None:
        return
    recorder = getattr(observer, "record_failure", None)
    if callable(recorder):
        await recorder(phase, error)


class CVEVerification(BaseModel):
    software: str = Field(min_length=1, max_length=200)
    vulnerable_version: str = Field(min_length=1, max_length=200)
    os_compatible: bool
    compatibility_reason: str = Field(min_length=1, max_length=2000)
    installation_artifact: Literal[
        "os_repository_package",
        "vendor_repository_package",
        "vendor_release_binary",
        "other_prebuilt",
        "source_build",
    ]
    artifact_source: str | None = Field(default=None, max_length=1000)
    source_build_reason: str | None = Field(default=None, max_length=2000)
    installation_method: str | None = Field(default=None, max_length=500)
    implementation_steps: list[str] = Field(default_factory=list, max_length=50)
    references: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def require_implementation_for_compatible_cve(self) -> CVEVerification:
        if self.os_compatible and (
            not self.installation_method
            or not self.implementation_steps
            or not self.artifact_source
        ):
            raise ValueError(
                "compatible CVE requires an installation method, artifact source, and steps"
            )
        if self.installation_artifact == "source_build" and not self.source_build_reason:
            raise ValueError("source build requires evidence that no compatible binary is available")
        return self


class AIGenerator(Protocol):
    async def plan_automatic_flags(
        self,
        machine: MachineInformation,
    ) -> AutomaticFlagPlan: ...

    async def generate_guidance(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        acquired_flags: list[str],
    ) -> GuidancePlan: ...

    async def generate_scenario(
        self,
        machine: MachineInformation,
        skills: ScenarioSkillContexts | None = None,
        on_attempt: Callable[[], Awaitable[None]] | None = None,
    ) -> ScenarioDraft: ...

    async def review_scenario(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        review_context: str = "generation",
        reconsideration: dict | None = None,
    ) -> ScenarioReview: ...

    async def generate_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        skills: SkillContext | None = None,
    ) -> GeneratedSource: ...

    async def repair_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        failure_report: dict,
        skills: SkillContext | None = None,
    ) -> SourcePatch: ...

    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision: ...

    async def synchronize_scenario(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        review_feedback: dict | None = None,
    ) -> ScenarioRevision: ...

    async def review_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        skills: SkillContext | None = None,
        reconsideration: dict | None = None,
    ) -> SourceReview: ...


class _BaseGenerator:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        *,
        model: str,
        max_output_tokens: int,
    ) -> None:
        self.settings = settings
        self.client = client
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.token_usage_recorder: TokenUsageRecorder | None = None

    def set_token_usage_recorder(self, recorder: TokenUsageRecorder) -> None:
        self.token_usage_recorder = recorder

    async def _record_token_usage(
        self, input_tokens: object, output_tokens: object, total_tokens: object
    ) -> None:
        session_id = _TOKEN_USAGE_SESSION_ID.get()
        if session_id is None or self.token_usage_recorder is None:
            return
        if not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in (input_tokens, output_tokens, total_tokens)
        ):
            logger.warning("AI provider returned invalid token usage metadata")
            return
        try:
            await self.token_usage_recorder(
                session_id, input_tokens, output_tokens, total_tokens
            )
        except Exception:
            logger.exception(
                "could not persist AI token usage", extra={"session_id": session_id}
            )

    async def _generate(
        self,
        prompt: str,
        *,
        json_output: bool = False,
        response_schema: type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError

    async def plan_automatic_flags(
        self,
        machine: MachineInformation,
    ) -> AutomaticFlagPlan:
        prompt = automatic_flag_plan_prompt(machine)
        last_error: Exception | None = None
        last_response: str | None = None
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=AutomaticFlagPlan,
                    max_output_tokens=min(self.max_output_tokens, 2_000),
                )
                last_response = response
                value = json.loads(response)
                raw_plan = (
                    value.get("flag_plan", value) if isinstance(value, dict) else value
                )
                return AutomaticFlagPlan.model_validate(raw_plan)
            except (
                httpx.HTTPError,
                RuntimeError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(
            f"Could not determine an automatic flag plan safely: {last_error}; "
            f"last output: {(last_response or '')[:2_000]}"
        )

    async def _draft_attack_graph(
        self,
        machine: MachineInformation,
        rejected: list[str],
        skill_context: str = "",
    ) -> AttackGraph:
        response = await self._generate(
            attack_graph_prompt(
                machine,
                rejected,
                self.settings.cve_min_year,
                skill_context,
            ),
            json_output=True,
            response_schema=AttackGraph,
            max_output_tokens=self.max_output_tokens,
        )
        try:
            value = json.loads(response)
            raw_graph = value.get("attack_graph", value) if isinstance(value, dict) else value
            raw_graph = self._normalize_attack_graph_payload(raw_graph)
            graph = AttackGraph.model_validate(raw_graph)
            self._validate_objectives(machine, graph)
            for step in graph.steps:
                if step.kind == "cve":
                    self._validate_cve_id(step.cve_id or "")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as error:
            raise _GeneratedArtifactValidationFailure(
                "attack_graph_draft", error, response
            ) from error
        return AttackGraph(objectives=self._expected_objectives(machine), steps=graph.steps)

    @staticmethod
    def _normalize_attack_graph_payload(raw_graph):
        """Remove CVE-only metadata accidentally attached to ordinary setup steps."""
        if not isinstance(raw_graph, dict) or not isinstance(raw_graph.get("steps"), list):
            return raw_graph
        cve_only_defaults = {
            "cve_title": None,
            "cve_description": None,
            "cwe_ids": [],
            "installation_artifact": None,
            "artifact_source": None,
            "source_build_reason": None,
        }
        for step in raw_graph["steps"]:
            if (
                isinstance(step, dict)
                and step.get("kind") != "cve"
                and not step.get("cve_id")
            ):
                for field_name, default in cve_only_defaults.items():
                    step[field_name] = default.copy() if isinstance(default, list) else default
            if isinstance(step, dict) and step.get("kind") != "password_cracking":
                step["password_cracking"] = None
        _BaseGenerator._clear_password_selections(raw_graph)
        return raw_graph

    @staticmethod
    def _clear_password_selections(raw_graph):
        if not isinstance(raw_graph, dict) or not isinstance(raw_graph.get("steps"), list):
            return raw_graph
        for step in raw_graph["steps"]:
            if not isinstance(step, dict):
                continue
            spec = step.get("password_cracking")
            if isinstance(spec, dict):
                spec["password"] = None
                spec["line_number"] = None
                spec["search_space_lines"] = None
        return raw_graph

    async def _revise_attack_graph(
        self,
        machine: MachineInformation,
        graph: AttackGraph,
        review: ScenarioReview,
    ) -> AttackGraph:
        last_error: Exception | None = None
        last_attempted_revision = None
        prompt = attack_graph_revision_prompt(
            machine,
            graph,
            _compact_scenario_review(review),
        )
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=AttackGraph,
                    max_output_tokens=self.max_output_tokens,
                )
                value = json.loads(response)
                raw_graph = value.get("attack_graph", value) if isinstance(value, dict) else value
                raw_graph = self._clear_password_selections(raw_graph)
                last_attempted_revision = raw_graph
                try:
                    revised = AttackGraph.model_validate(raw_graph)
                except ValidationError as error:
                    if any(item["type"] == "value_error" for item in error.errors()):
                        raise _GeneratedArtifactValidationFailure(
                            "attack_graph_revision", error, raw_graph
                        ) from error
                    raise
                try:
                    self._validate_attack_graph_revision(graph, revised)
                    if revised == graph:
                        raise ValueError("attack graph revision made no change")
                    self._validate_objectives(machine, revised)
                except ValueError as error:
                    raise _GeneratedArtifactValidationFailure(
                        "attack_graph_revision", error, raw_graph
                    ) from error
                return revised
            except _GeneratedArtifactValidationFailure:
                raise
            except (
                httpx.HTTPError,
                RuntimeError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        if isinstance(last_error, ValidationError):
            raise _GeneratedArtifactValidationFailure(
                "attack_graph_revision", last_error, last_attempted_revision
            ) from last_error
        raise RuntimeError(f"Could not revise attack graph safely: {last_error}")

    async def _parse_or_compact_scenario_generation(
        self,
        machine: MachineInformation,
        response: str,
    ) -> ScenarioGeneration:
        value = json.loads(response)
        if not isinstance(value, dict):
            return ScenarioGeneration.model_validate(value)
        scenario_description = value.get("scenario_description")
        definition = value.get("definition")
        if not (
            isinstance(scenario_description, str)
            and isinstance(definition, str)
            and len(definition) > SCENARIO_DEFINITION_TARGET_CHARS
        ):
            return ScenarioGeneration.model_validate(value)

        last_error: Exception | None = None
        prompt = scenario_compaction_prompt(machine, scenario_description, definition)
        for _ in range(self.settings.generation_retries):
            compacted_response: str | None = None
            try:
                compacted_response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=ScenarioGeneration,
                    max_output_tokens=self.max_output_tokens,
                )
                compacted = ScenarioGeneration.model_validate_json(compacted_response)
                if len(compacted.definition) > SCENARIO_DEFINITION_TARGET_CHARS:
                    raise ValueError(
                        "compacted scenario definition exceeds target length "
                        f"{SCENARIO_DEFINITION_TARGET_CHARS}"
                    )
                return compacted
            except (
                httpx.HTTPError,
                RuntimeError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, compacted_response)
        if isinstance(last_error, (TypeError, ValueError, ValidationError)):
            raise _GeneratedArtifactValidationFailure(
                "scenario_compaction", last_error, compacted_response
            ) from last_error
        raise ValueError(f"Could not compact scenario definition: {last_error}")

    async def _correct_scenario(
        self,
        machine: MachineInformation,
        graph: AttackGraph,
        previous: ScenarioDraft,
        review_feedback: list[str],
        skill_context: str,
    ) -> ScenarioDraft:
        last_error: Exception | None = None
        last_attempted_correction: str | None = None
        prompt = scenario_correction_prompt(
            machine,
            graph,
            previous,
            review_feedback,
            skill_context,
        )
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=ScenarioCorrection,
                    max_output_tokens=self.max_output_tokens,
                )
                last_attempted_correction = response
                correction = ScenarioCorrection.model_validate_json(response)
                definition = previous.definition
                for replacement in correction.definition_replacements:
                    occurrences = definition.count(replacement.old)
                    if occurrences != 1:
                        raise ValueError(
                            "scenario correction old text must occur exactly once: "
                            f"found {occurrences} occurrences; rejected old="
                            + json.dumps(replacement.old[:1_000], ensure_ascii=False)
                        )
                    if replacement.old == definition:
                        raise ValueError("scenario correction must not replace the whole document")
                    definition = definition.replace(replacement.old, replacement.new, 1)
                if len(definition) > SCENARIO_DEFINITION_MAX_CHARS:
                    raise ValueError(
                        "corrected scenario definition exceeds "
                        f"{SCENARIO_DEFINITION_MAX_CHARS} characters"
                    )
                scenario_description = (
                    correction.scenario_description
                    if correction.scenario_description is not None
                    else previous.scenario_description
                )
                if (
                    definition == previous.definition
                    and scenario_description == previous.scenario_description
                    and graph == previous.attack_graph
                ):
                    raise ValueError("scenario correction did not change the rejected draft")
                return previous.model_copy(
                    update={
                        "title": machine.name,
                        "scenario_description": scenario_description,
                        "definition": definition,
                        "target_os": machine.operating_system,
                        "attack_graph": graph,
                    }
                )
            except (
                httpx.HTTPError,
                RuntimeError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        if isinstance(last_error, (KeyError, TypeError, ValueError, ValidationError)):
            raise _GeneratedArtifactValidationFailure(
                "scenario_correction", last_error, last_attempted_correction
            ) from last_error
        raise ValueError(f"Could not apply scenario review as a minimal patch: {last_error}")

    @staticmethod
    def _validate_attack_graph_revision(
        original: AttackGraph,
        revised: AttackGraph,
    ) -> None:
        if revised.objectives != original.objectives:
            raise ValueError("attack graph revision must not change objectives")
        if len(revised.steps) != len(original.steps):
            raise ValueError("attack graph revision must not add or remove steps")

        for original_step, revised_step in zip(original.steps, revised.steps, strict=True):
            original_data = original_step.model_dump(mode="json")
            revised_data = revised_step.model_dump(mode="json")
            changed_immutable = [
                field_name
                for field_name, original_value in original_data.items()
                if field_name not in ATTACK_GRAPH_REVISION_FIELDS
                and revised_data.get(field_name) != original_value
            ]
            if changed_immutable:
                raise ValueError(
                    "attack graph revision changed immutable fields for "
                    f"{original_step.step_id}: {', '.join(changed_immutable)}"
                )

    @staticmethod
    def _review_requires_graph_revision(review: ScenarioReview) -> bool:
        return any(
            finding.severity == "error" and finding.repair_target == "attack_graph"
            for finding in review.findings
        )

    @staticmethod
    def _review_requires_graph_regeneration(review: ScenarioReview) -> bool:
        return any(
            finding.severity == "error"
            and (
                finding.category == "broken_chain"
                or finding.repair_target == "attack_graph_regeneration"
            )
            for finding in review.findings
        )

    @staticmethod
    def _raise_for_user_input(review: ScenarioReview) -> None:
        findings = [
            finding.model_dump(mode="json")
            for finding in review.findings
            if finding.severity == "error" and finding.repair_target == "user_input"
        ]
        if findings:
            raise ScenarioInputRevisionRequiredError(review.summary, findings)

    async def _reconsider_scenario_review(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        previous_review: ScenarioReview,
        failure: _GeneratedArtifactValidationFailure,
        signatures: set[str],
        on_attempt: Callable[[], Awaitable[None]] | None,
    ) -> ScenarioReview:
        signature = json.dumps(
            {
                "artifact_kind": failure.artifact_kind,
                "review": _compact_scenario_review(previous_review),
                "validation_error": failure.validation_error,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if signature in signatures or len(signatures) >= MAX_REVIEW_RECONSIDERATIONS:
            raise _ReviewReconsiderationExhausted(
                "review reconsideration repeated the same invalid repair"
            ) from failure
        signatures.add(signature)
        reconsidered = await self.review_scenario(
            machine,
            scenario,
            reconsideration={
                "kind": f"{failure.artifact_kind}_validation_failure",
                "previous_review": _compact_scenario_review(previous_review),
                "validation_error": failure.validation_error[:4_000],
                "attempted_output": failure.attempted_output,
            },
        )
        await _record_scenario_draft(on_attempt, scenario, reconsidered)
        self._raise_for_user_input(reconsidered)
        return reconsidered

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
        match = re.fullmatch(r"debian\s+(\d+)(?:\.\d+){0,2}", target_os.strip(), re.IGNORECASE)
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
            "state": record.get("cveMetadata", {}).get("state"),
            "title": cna.get("title"),
            "descriptions": cna.get("descriptions", [])[:3],
            "problem_types": cna.get("problemTypes", [])[:20],
            "affected": cna.get("affected", [])[:20],
            "metrics": cna.get("metrics", [])[:10],
            "references": [item.get("url") for item in cna.get("references", [])[:20]],
            "debian_osv": debian,
            "public_poc_repositories": refs,
            "official_cve_url": f"https://www.cve.org/CVERecord?id={cve_id}",
        }

    @staticmethod
    def _official_cve_facts(cve_id: str, evidence: dict) -> dict[str, object]:
        state = str(evidence.get("state") or "").upper()
        if state and state != "PUBLISHED":
            raise ValueError(f"{cve_id} is not published (state={state})")
        title = str(evidence.get("title") or "").strip()
        descriptions = evidence.get("descriptions") or []
        description = next(
            (
                str(item.get("value") or "").strip()
                for item in descriptions
                if isinstance(item, dict)
                and str(item.get("lang") or "").lower().startswith("en")
                and str(item.get("value") or "").strip()
            ),
            "",
        )
        if not description:
            description = next(
                (
                    str(item.get("value") or "").strip()
                    for item in descriptions
                    if isinstance(item, dict) and str(item.get("value") or "").strip()
                ),
                "",
            )
        if not description:
            raise ValueError(f"{cve_id} official record is missing a description")
        if not title:
            # A CNA title is optional in the CVE record schema.  Keep the
            # downstream display title deterministic and grounded in the
            # official record by deriving it from the first description
            # sentence instead of asking the model to invent one.
            normalized_description = re.sub(r"\s+", " ", description).strip()
            title = re.split(
                r"(?<=[.!?])\s+", normalized_description, maxsplit=1
            )[0]
        cwe_ids: list[str] = []
        for problem in evidence.get("problem_types") or []:
            if not isinstance(problem, dict):
                continue
            for item in problem.get("descriptions") or []:
                if not isinstance(item, dict):
                    continue
                cwe_id = str(item.get("cweId") or "").strip().upper()
                if re.fullmatch(r"CWE-\d+", cwe_id) and cwe_id not in cwe_ids:
                    cwe_ids.append(cwe_id)
        references = [
            url
            for url in [*(evidence.get("references") or []), evidence.get("official_cve_url")]
            if isinstance(url, str) and url.strip()
        ]
        return {
            "title": title[:500],
            "description": description[:4000],
            "cwe_ids": cwe_ids,
            "references": list(dict.fromkeys(references))[:30],
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
        official = self._official_cve_facts(step.cve_id, evidence)
        prompt = f"""次の攻撃グラフ内のCVEステップを、公式CVEレコードと対象OSの証拠に基づいて
検証し、隔離された教育VMへ脆弱な状態を構築する計画をJSONで返してください。

対象OS: {machine.operating_system}
攻撃ステップ:
{step.model_dump_json(indent=2)}
証拠:
{json.dumps(evidence, ensure_ascii=False)}

JSONのみを返してください:
{{"software":"...","vulnerable_version":"...","os_compatible":true,
"compatibility_reason":"...","installation_artifact":"os_repository_package",
"artifact_source":"取得元のリポジトリまたは公式配布元","source_build_reason":null,
"installation_method":"...",
"implementation_steps":["取得","固定","設定","起動確認"],"references":["..."]}}

規則:
- 攻撃ステップの元のtitle、description、実装案は未検証であり、公式証拠と矛盾する場合は無視する
- 公式レコードに記載された脆弱性メカニズムと必要条件そのものを再現する。別の設定不備、別の脆弱性、
  模擬エンドポイント、CVEとは無関係なRCEへ置き換えない
- 公式メカニズムを対象OS上で再現・検証できない場合は、別手法を捏造せずos_compatible=falseにする
- 導入方法は、(1)対象Debianの通常またはsnapshotリポジトリにあるバージョン固定パッケージ、
  (2)ベンダー公式リポジトリのパッケージ、(3)ベンダー公式releaseのビルド済みバイナリ、
  (4)信頼できる既存のビルド済み成果物、(5)ソースビルド、の順で調査・選択する
- 最新パッケージで脆弱版を置き換えず、選択した成果物がvulnerable_versionと一致することを
  インストール後に検証する。アーキテクチャ、依存関係、checksumまたは署名も検証計画へ含める
- source_buildは先行する全バイナリ経路が対象OS・アーキテクチャ・脆弱版に対応しない場合だけ選び、
  調査した配布元と利用できない理由をsource_build_reasonへ具体的に記載する
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
        self._enforce_debian_package_evidence(verification, evidence)
        if not verification.os_compatible:
            raise ValueError(
                f"{step.cve_id} is not compatible with {machine.operating_system}: "
                f"{verification.compatibility_reason}"
            )
        values = step.model_dump(mode="json")
        values.update(verification.model_dump(mode="json"))
        values.update(
            {
                "title": f"{step.cve_id}: {official['title']}"[:200],
                "description": official["description"],
                "cve_title": official["title"],
                "cve_description": official["description"],
                "cwe_ids": official["cwe_ids"],
                "references": list(
                    dict.fromkeys(
                        [*official["references"], *verification.references]
                    )
                )[:30],
            }
        )
        return AttackStep.model_validate(values)

    @staticmethod
    def _enforce_debian_package_evidence(
        verification: CVEVerification, evidence: dict
    ) -> None:
        debian = evidence.get("debian_osv")
        if (
            verification.installation_artifact == "os_repository_package"
            and debian is not None
            and not debian["affected"]
        ):
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

    async def generate_scenario(
        self,
        machine: MachineInformation,
        skills: ScenarioSkillContexts | None = None,
        on_attempt: Callable[[], Awaitable[None]] | None = None,
    ) -> ScenarioDraft:
        resolved_skills = skills or ScenarioSkillContexts()
        for requested_id in SkillSelector.cve_ids(machine):
            self._validate_cve_id(requested_id)
        for skill in resolved_skills.attack_graph.skills:
            if skill.name == "cve":
                for reference_id in skill.selected_reference_ids:
                    self._validate_cve_id(reference_id)
        attack_graph_skills = SkillRenderer.render(resolved_skills.attack_graph)
        last_error: Exception | None = None
        rejected: list[str] = []
        previous_scenario = getattr(on_attempt, "resume_scenario", None)
        previous_review = getattr(on_attempt, "resume_review", None)
        if not isinstance(previous_scenario, ScenarioDraft):
            previous_scenario = None
        if not isinstance(previous_review, ScenarioReview):
            previous_review = None
        graph: AttackGraph | None = (
            previous_scenario.attack_graph if previous_scenario is not None else None
        )
        pending_graph_review: ScenarioReview | None = None
        pending_scenario_review: ScenarioReview | None = None
        reconsideration_signatures: set[str] = set()
        if graph is not None:
            try:
                self._validate_objectives(machine, graph)
                self._validate_skill_cves(graph, resolved_skills, machine)
            except ValueError as error:
                rejected.append(f"persisted scenario is no longer compatible: {error}")
                previous_scenario = None
                previous_review = None
                graph = None
        if previous_scenario is not None and previous_review is None:
            previous_review = await self.review_scenario(machine, previous_scenario)
            await _record_scenario_draft(on_attempt, previous_scenario, previous_review)
        if previous_scenario is not None and previous_review is not None:
            self._raise_for_user_input(previous_review)
            if previous_review.approved:
                return previous_scenario
            review_report = _compact_scenario_review(previous_review)
            rejected.append(
                "scenario_semantic_review: " + json.dumps(review_report, ensure_ascii=False)
            )
            last_error = ValueError(
                f"scenario semantic review failed: {previous_review.summary}"
            )
            pending_scenario_review = previous_review
            if self._review_requires_graph_regeneration(previous_review):
                graph = None
            elif graph is not None and self._review_requires_graph_revision(previous_review):
                pending_graph_review = previous_review
        for _ in range(self.settings.scenario_generation_attempts):
            if on_attempt is not None:
                await on_attempt()
            attempt_phase = "attack_graph_generation"
            graph_changed_this_attempt = False
            try:
                if graph is None:
                    candidate = await self._draft_attack_graph(
                        machine, rejected, attack_graph_skills
                    )
                    self._validate_skill_cves(candidate, resolved_skills, machine)
                    graph = await self._verify_attack_graph(machine, candidate)
                    pending_graph_review = None
                    graph_changed_this_attempt = previous_scenario is not None
                elif pending_graph_review is not None:
                    try:
                        graph = await self._revise_attack_graph(
                            machine,
                            graph,
                            pending_graph_review,
                        )
                    except _GeneratedArtifactValidationFailure as error:
                        if previous_scenario is None:
                            raise
                        reconsidered = await self._reconsider_scenario_review(
                            machine,
                            previous_scenario,
                            pending_graph_review,
                            error,
                            reconsideration_signatures,
                            on_attempt,
                        )
                        if reconsidered.approved:
                            return previous_scenario
                        review_report = _compact_scenario_review(reconsidered)
                        rejected.append(
                            "scenario_review_reconsideration: "
                            + json.dumps(review_report, ensure_ascii=False)
                        )
                        last_error = error
                        pending_scenario_review = reconsidered
                        if self._review_requires_graph_regeneration(reconsidered):
                            graph = None
                            pending_graph_review = None
                        elif self._review_requires_graph_revision(reconsidered):
                            pending_graph_review = reconsidered
                        else:
                            pending_graph_review = None
                        continue
                    self._validate_skill_cves(graph, resolved_skills, machine)
                    if previous_scenario is not None:
                        previous_scenario = previous_scenario.model_copy(
                            update={"attack_graph": graph}
                        )
                        await _record_scenario_draft(on_attempt, previous_scenario)
                    pending_graph_review = None
                    graph_changed_this_attempt = True
                await _record_attack_graph(on_attempt, graph)
                attempt_phase = "scenario_generation"
                scenario_skill_context = SkillRenderer.render(
                    context_for_graph(resolved_skills.scenario, graph)
                )
                if previous_scenario is None:
                    response = await self._generate(
                        scenario_prompt(
                            machine,
                            attack_graph_json_for_ai(graph),
                            review_feedback=rejected,
                            skill_context=scenario_skill_context,
                        ),
                        json_output=True,
                        response_schema=ScenarioGeneration,
                        max_output_tokens=self.max_output_tokens,
                    )
                    try:
                        generated = await self._parse_or_compact_scenario_generation(
                            machine,
                            response,
                        )
                    except _GeneratedArtifactValidationFailure:
                        raise
                    except (
                        KeyError,
                        TypeError,
                        ValueError,
                        json.JSONDecodeError,
                        ValidationError,
                    ) as error:
                        raise _GeneratedArtifactValidationFailure(
                            "scenario_generation", error, response
                        ) from error
                    scenario = ScenarioDraft(
                        scenario_id=f"scenario-{uuid4().hex}",
                        title=machine.name,
                        scenario_description=generated.scenario_description,
                        definition=generated.definition,
                        target_os=machine.operating_system,
                        attack_graph=graph,
                    )
                else:
                    active_review_feedback = (
                        [
                            "scenario_semantic_review: "
                            + json.dumps(
                                _compact_scenario_review(pending_scenario_review),
                                ensure_ascii=False,
                            )
                        ]
                        if pending_scenario_review is not None
                        else rejected[-1:]
                    )
                    try:
                        scenario = await self._correct_scenario(
                            machine,
                            graph,
                            previous_scenario,
                            active_review_feedback,
                            scenario_skill_context,
                        )
                    except _GeneratedArtifactValidationFailure as error:
                        if pending_scenario_review is None:
                            raise
                        reconsidered = await self._reconsider_scenario_review(
                            machine,
                            previous_scenario,
                            pending_scenario_review,
                            error,
                            reconsideration_signatures,
                            on_attempt,
                        )
                        if reconsidered.approved:
                            return previous_scenario
                        review_report = _compact_scenario_review(reconsidered)
                        rejected.append(
                            "scenario_review_reconsideration: "
                            + json.dumps(review_report, ensure_ascii=False)
                        )
                        last_error = error
                        pending_scenario_review = reconsidered
                        if self._review_requires_graph_regeneration(reconsidered):
                            graph = None
                            pending_graph_review = None
                        elif self._review_requires_graph_revision(reconsidered):
                            pending_graph_review = reconsidered
                        continue
                previous_scenario = scenario
                await _record_scenario_draft(on_attempt, scenario)
                attempt_phase = "scenario_review"
                repair_scope = (
                    pending_scenario_review
                    if pending_scenario_review is not None and not graph_changed_this_attempt
                    else None
                )
                review = await self.review_scenario(
                    machine,
                    scenario,
                    review_context=(
                        "repair_verification" if repair_scope is not None else "generation"
                    ),
                    reconsideration=(
                        {
                            "kind": "scenario_repair_verification",
                            "blocking_review": _compact_scenario_review(repair_scope),
                        }
                        if repair_scope is not None
                        else None
                    ),
                )
                await _record_scenario_draft(on_attempt, scenario, review)
                self._raise_for_user_input(review)
                if review.approved:
                    return scenario
                review_report = _compact_scenario_review(review)
                last_error = ValueError(f"scenario semantic review failed: {review.summary}")
                pending_scenario_review = review
                rejected.append(
                    "scenario_semantic_review: " + json.dumps(review_report, ensure_ascii=False)
                )
                if self._review_requires_graph_regeneration(review):
                    graph = None
                    pending_graph_review = None
                elif self._review_requires_graph_revision(review):
                    pending_graph_review = review
            except ScenarioInputRevisionRequiredError:
                raise
            except _ReviewReconsiderationExhausted as error:
                await _record_scenario_failure(on_attempt, attempt_phase, error)
                raise RuntimeError(
                    "Scenario review repeated a repair that could not pass "
                    "attack-graph validation"
                ) from error
            except (
                httpx.HTTPError,
                RuntimeError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as error:
                last_error = error
                rejected.append(_generated_artifact_failure_feedback(error))
                await _record_scenario_failure(on_attempt, attempt_phase, error)
        raise RuntimeError(f"Could not generate an approved scenario: {last_error}")

    async def review_scenario(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        review_context: str = "generation",
        reconsideration: dict | None = None,
    ) -> ScenarioReview:
        last_error: Exception | None = None
        prompt = scenario_review_prompt(
            machine,
            scenario,
            review_context,
            reconsideration,
        )
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=ScenarioReview,
                    max_output_tokens=self.max_output_tokens,
                )
                review = ScenarioReview.model_validate_json(response)
                self._validate_scenario_review(review, scenario, review_context)
                return _discard_framework_owned_scenario_findings(review, scenario)
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(f"Could not review scenario: {last_error}")

    @staticmethod
    def _validate_scenario_review(
        review: ScenarioReview,
        scenario: ScenarioDraft,
        review_context: str,
    ) -> None:
        step_by_id = {step.step_id: step for step in scenario.attack_graph.steps}
        for finding in review.findings:
            if finding.step_id is not None and finding.step_id not in step_by_id:
                raise ValueError(
                    f"scenario review references unknown step_id: {finding.step_id}"
                )
            if (
                finding.repair_target in {"attack_graph", "attack_graph_regeneration"}
                and finding.step_id is None
            ):
                raise ValueError(
                    f"{finding.repair_target} finding requires a known step_id"
                )
            if (
                finding.repair_target == "attack_graph_regeneration"
                and finding.category not in {"broken_chain", "unsupported_assumption"}
            ):
                raise ValueError(
                    "attack_graph_regeneration is only valid for an independently broken "
                    "dependency graph or an unsupported graph assumption; prose mismatches "
                    "must target scenario_text"
                )
            if finding.repair_target == "user_input" and (
                finding.category != "input_contradiction" or finding.step_id is not None
            ):
                raise ValueError(
                    "user_input is only valid for an explicit input_contradiction without "
                    "a generated attack-graph step_id"
                )
            if (
                finding.category == "input_contradiction"
                and finding.repair_target != "user_input"
            ):
                raise ValueError(
                    "input_contradiction findings must target user_input"
                )
            if finding.repair_target == "source_code" and review_context != "source_sync":
                raise ValueError(
                    "source_code findings are only valid during source_sync review"
                )
            if finding.step_id is None:
                continue
            step = step_by_id[finding.step_id]
            cve_only = {
                "installation_artifact",
                "artifact_source",
                "source_build_reason",
                "cve_title",
                "cve_description",
                "cwe_ids",
            }
            if step.kind != "cve" and cve_only.intersection(finding.repair_fields):
                raise ValueError(
                    f"scenario review requests CVE-only fields for non-CVE step {step.step_id}"
                )

    @staticmethod
    def _validate_skill_cves(
        graph: AttackGraph, skills: ScenarioSkillContexts, machine: MachineInformation
    ) -> None:
        required = set(SkillSelector.cve_ids(machine))
        actual = {step.cve_id for step in graph.steps if step.cve_id}
        if not required <= actual:
            raise ValueError(f"Attack graph must use requested CVEs: {sorted(required - actual)}")
        try:
            context_for_graph(skills.attack_graph, graph)
        except ValueError as error:
            raise ValueError(
                f"Attack graph must use the selected CVE references: {error}"
            ) from error

    async def generate_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        skills: SkillContext | None = None,
    ) -> GeneratedSource:
        last_error: Exception | None = None
        skill_context = SkillRenderer.render(skills or SkillContext(phase=SkillPhase.SOURCE))
        prompt = code_prompt(machine, scenario, skill_context)
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=GeneratedSource,
                    max_output_tokens=self.max_output_tokens,
                )
                generated = GeneratedSource.model_validate_json(response)
                _validate_generated_file_payload(generated.files)
                return generated
            except (httpx.HTTPError, RuntimeError, TypeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(f"Could not generate valid VM source: {last_error}")

    async def generate_guidance(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        acquired_flags: list[str],
    ) -> GuidancePlan:
        last_error: Exception | None = None
        prompt = guidance_prompt(machine, scenario, current, acquired_flags)
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=GuidancePlan,
                    max_output_tokens=min(self.max_output_tokens, 4096),
                )
                guidance = GuidancePlan.model_validate_json(response)
                serialized = guidance.model_dump_json().casefold()
                if any(
                    flag and flag.casefold() in serialized
                    for flag in (scenario.user_flag, scenario.system_flag)
                ):
                    raise ValueError("guidance must not expose a correct flag value")
                allowed_targets = {
                    kind
                    for kind, flag in (
                        ("user", scenario.user_flag),
                        ("system", scenario.system_flag),
                    )
                    if flag and kind not in acquired_flags
                }
                actual_targets = {item.target_flag for item in guidance.items}
                if not actual_targets <= allowed_targets:
                    raise ValueError("guidance targets a missing or acquired flag")
                if missing_targets := allowed_targets - actual_targets:
                    raise ValueError(
                        "guidance is missing items for unsolved flags: "
                        + ", ".join(sorted(missing_targets))
                    )
                return guidance
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(f"Could not generate safe guidance: {last_error}")

    async def repair_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        failure_report: dict,
        skills: SkillContext | None = None,
    ) -> SourcePatch:
        last_error: Exception | None = None
        retry_report = failure_report
        skill_context = SkillRenderer.render(skills or SkillContext(phase=SkillPhase.REPAIR))
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    repair_prompt(
                        machine,
                        scenario,
                        current,
                        retry_report,
                        skill_context,
                    ),
                    json_output=True,
                    response_schema=SourcePatch,
                    max_output_tokens=self.max_output_tokens,
                )
                patch = SourcePatch.model_validate_json(response)
                _validate_generated_file_payload(patch.files)
                return patch
            except (httpx.HTTPError, RuntimeError, TypeError, ValueError) as error:
                last_error = error
                retry_report = {
                    **failure_report,
                    "model_output_validation_error": str(error),
                    "rejected_model_output": response[:12_000] if response else None,
                }
        raise RuntimeError(f"Could not repair VM source: {last_error}")

    async def next_source_workbench_action(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        observations: list[dict],
        commands_remaining: int,
    ) -> SourceWorkbenchDecision:
        last_error: Exception | None = None
        prompt = source_workbench_prompt(
            machine,
            scenario,
            current,
            observations,
            commands_remaining=commands_remaining,
        )
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=SourceWorkbenchDecision,
                    max_output_tokens=min(self.max_output_tokens, 16_384),
                )
                decision = SourceWorkbenchDecision.model_validate_json(response)
                if decision.patch is not None:
                    _validate_generated_file_payload(decision.patch.files)
                return decision
            except (httpx.HTTPError, RuntimeError, TypeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(f"Could not choose a source workbench action: {last_error}")

    async def synchronize_scenario(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        review_feedback: dict | None = None,
    ) -> ScenarioRevision:
        last_error: Exception | None = None
        prompt = scenario_sync_prompt(machine, scenario, current, review_feedback)
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=ScenarioTextRevision,
                    max_output_tokens=self.max_output_tokens,
                )
                text_revision = ScenarioTextRevision.model_validate_json(response)
                revision = ScenarioRevision(
                    scenario_description=text_revision.scenario_description,
                    definition=text_revision.definition,
                    attack_graph=scenario.attack_graph,
                    summary=text_revision.summary,
                )
                revision_text = (
                    revision.scenario_description
                    + "\n"
                    + revision.definition
                ).casefold()
                for flag in (scenario.user_flag, scenario.system_flag):
                    if flag and flag.casefold() in revision_text:
                        raise ValueError("scenario revision must not expose a correct flag value")
                return revision
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(f"Could not synchronize scenario with VM source: {last_error}")

    async def review_source(
        self,
        machine: MachineInformation,
        scenario: ScenarioDraft,
        current: GeneratedSource,
        skills: SkillContext | None = None,
        reconsideration: dict | None = None,
    ) -> SourceReview:
        last_error: Exception | None = None
        skill_context = SkillRenderer.render(skills or SkillContext(phase=SkillPhase.REVIEW))
        prompt = source_review_prompt(
            machine,
            scenario,
            current,
            skill_context,
            reconsideration,
        )
        for _ in range(self.settings.generation_retries):
            response: str | None = None
            try:
                response = await self._generate(
                    prompt,
                    json_output=True,
                    response_schema=SourceReview,
                    max_output_tokens=self.max_output_tokens,
                )
                review = SourceReview.model_validate_json(response)
                return _discard_framework_owned_source_findings(review, scenario)
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                last_error = error
                prompt = _prompt_with_rejection(prompt, error, response)
        raise RuntimeError(f"Could not review VM source: {last_error}")


def _is_framework_owned_password_selection_finding(
    finding,
    password_step_ids: set[str],
) -> bool:
    if finding.step_id not in password_step_ids:
        return False
    text = f"{finding.evidence}\n{finding.remediation}".casefold()
    wordlist_terms = (
        "rockyou",
        "wordlist",
        "ワードリスト",
        "辞書ファイル",
    )
    selection_infrastructure_terms = (
        "取得",
        "入手",
        "配置",
        "配置先",
        "受け渡し",
        "存在",
        "ファイルパス",
        "参照先",
        "checksum",
        "整合性",
        "含まれ",
        "line_number",
        "search_space_lines",
        "download",
        "location",
        "provisioning input",
    )
    benchmark_terms = (
        "測定",
        "ベンチマーク",
        "ハードウェア",
        "実行環境",
        "探索時間",
        "クラック時間",
        "target_crack_seconds",
        "benchmark",
        "hardware",
        "cpu",
        "gpu",
    )
    benchmark_context_terms = (
        "hashcat",
        "john",
        "秒",
        "探索時間",
        "クラック時間",
        "速度",
        "候補選定",
        "crack",
    )
    requests_wordlist_infrastructure = any(term in text for term in wordlist_terms) and any(
        term in text for term in selection_infrastructure_terms
    )
    requests_selection_benchmark = any(term in text for term in benchmark_terms) and any(
        term in text for term in benchmark_context_terms
    )
    return requests_wordlist_infrastructure or requests_selection_benchmark


def _password_cracking_step_ids(scenario: ScenarioDraft) -> set[str]:
    return {
        step.step_id
        for step in scenario.attack_graph.steps
        if step.password_cracking is not None
    }


def _requests_third_party_poc(finding) -> bool:
    if finding.category not in {"acceptance_test_gap", "unproven_exploit"}:
        return False
    text = f"{finding.evidence}\n{finding.remediation}".casefold()
    remediation = finding.remediation.casefold()
    poc_terms = (
        "poc",
        "proof of concept",
        "proof-of-concept",
        "exploit-db",
        "exploitdb",
        "packet storm",
        "packetstorm",
        "metasploit",
        "公開 exploit",
        "公開エクスプロイト",
        "野良 exploit",
        "野良エクスプロイト",
    )
    removal_terms = ("remove", "delete", "削除", "除去", "使わない", "実行しない")
    return any(term in text for term in poc_terms) and not any(
        term in remediation for term in removal_terms
    )


def _optional_exploit_finding(finding):
    if finding.severity != "error" or not _requests_third_party_poc(finding):
        return finding, False
    return (
        finding.model_copy(
            update={
                "severity": "warning",
                "remediation": (
                    "第三者PoCを自動テストやサンドボックスで取得・実行しないでください。"
                    "READMEで攻略者へ入手を案内することはできます。生成物だけで安全な"
                    "自己完結テストを作れなければ、攻撃固有の自動検証は省略できます。"
                ),
            }
        ),
        True,
    )


def _discard_framework_owned_scenario_findings(
    review: ScenarioReview,
    scenario: ScenarioDraft,
) -> ScenarioReview:
    """Remove findings that ask generated artifacts to revalidate server-owned secrets."""

    password_step_ids = _password_cracking_step_ids(scenario)
    retained = []
    discarded = 0
    downgraded = 0
    for finding in review.findings:
        if _is_framework_owned_password_selection_finding(finding, password_step_ids):
            discarded += 1
            continue
        normalized, changed = _optional_exploit_finding(finding)
        retained.append(normalized)
        downgraded += int(changed)

    if not discarded and not downgraded:
        return review
    has_error = any(finding.severity == "error" for finding in retained)
    return ScenarioReview(
        approved=not has_error,
        summary=(
            review.summary
            + f" Removed {discarded} finding(s) about framework-owned password selection."
            + f" Downgraded {downgraded} optional exploit-verification finding(s)."
        ),
        findings=retained,
    )


def _discard_framework_owned_source_findings(
    review: SourceReview,
    scenario: ScenarioDraft,
) -> SourceReview:
    password_step_ids = _password_cracking_step_ids(scenario)
    retained = []
    discarded = 0
    downgraded = 0
    for finding in review.findings:
        if _is_framework_owned_password_selection_finding(finding, password_step_ids):
            discarded += 1
            continue
        normalized, changed = _optional_exploit_finding(finding)
        retained.append(normalized)
        downgraded += int(changed)
    if not discarded and not downgraded:
        return review
    has_error = any(finding.severity == "error" for finding in retained)
    return SourceReview(
        approved=not has_error,
        summary=(
            review.summary
            + f" Removed {discarded} finding(s) about framework-owned password selection."
            + f" Downgraded {downgraded} optional exploit-verification finding(s)."
        ),
        findings=retained,
    )


class GeminiGenerator(_BaseGenerator):
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        super().__init__(
            settings,
            client,
            model=settings.gemini_model,
            max_output_tokens=settings.gemini_max_output_tokens,
        )

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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
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
        body = response.json()
        usage = body.get("usageMetadata", {})
        if isinstance(usage, dict):
            await self._record_token_usage(
                usage.get("promptTokenCount"),
                usage.get("candidatesTokenCount"),
                usage.get("totalTokenCount"),
            )
        prompt_feedback = body.get("promptFeedback", {})
        block_reason = (
            prompt_feedback.get("blockReason") if isinstance(prompt_feedback, dict) else None
        )
        if block_reason and block_reason != "BLOCK_REASON_UNSPECIFIED":
            raise AIProviderSafetyRefusalError("Gemini", block_reason)
        candidates = body.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        finish_reason = candidates[0].get("finishReason")
        if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise AIProviderSafetyRefusalError("Gemini", finish_reason)
        if finish_reason and finish_reason != "STOP":
            raise RuntimeError(f"Gemini generation stopped with {finish_reason}")
        parts = candidates[0].get("content", {}).get("parts", [])
        if any("functionCall" in part for part in parts):
            raise RuntimeError("Gemini requested an unavailable function tool")
        generated_text = "".join(part.get("text", "") for part in parts).strip()
        if not generated_text:
            raise RuntimeError("Gemini returned an empty response")
        return generated_text


class OpenAIGenerator(_BaseGenerator):
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        super().__init__(
            settings,
            client,
            model=settings.openai_model,
            max_output_tokens=settings.openai_max_output_tokens,
        )
        self._request_gate = _SharedAIRequestGate(
            settings.ai_max_concurrent_requests,
            settings.ai_request_min_interval_seconds,
        )

    @staticmethod
    def _error_metadata(response: httpx.Response) -> tuple[str | None, str | None, str]:
        detail = response.text.strip()[:2000]
        try:
            body = response.json()
        except (json.JSONDecodeError, TypeError, ValueError):
            return None, None, detail
        error = body.get("error") if isinstance(body, dict) else None
        if not isinstance(error, dict):
            return None, None, detail
        error_type = error.get("type")
        error_code = error.get("code")
        return (
            error_type if isinstance(error_type, str) else None,
            error_code if isinstance(error_code, str) else None,
            detail,
        )

    @staticmethod
    def _is_retryable_response(
        response: httpx.Response,
        error_type: str | None,
        error_code: str | None,
    ) -> bool:
        if response.status_code == 429:
            permanent_codes = {
                "billing_hard_limit_reached",
                "credit_balance_exhausted",
                "insufficient_quota",
                "organization_spend_limit_exceeded",
                "organization_usage_limit_exceeded",
                "project_spend_limit_exceeded",
                "usage_limit_reached",
            }
            if error_code in permanent_codes:
                return False
            if error_type in {
                "authentication_error",
                "billing_error",
                "insufficient_quota",
                "invalid_request_error",
            }:
                return error_code == "rate_limit_exceeded"
            return True
        return response.status_code in {408, 500, 502, 503, 504}

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            seconds = (retry_at - datetime.now(UTC)).total_seconds()
        if seconds < 0:
            return 0.0
        return seconds

    async def _post_with_retry(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> httpx.Response:
        loop = asyncio.get_running_loop()
        started = loop.time()
        attempts = self.settings.ai_transient_retry_attempts
        max_elapsed = self.settings.ai_transient_retry_max_seconds
        request_id = str(uuid4())
        request_headers = {**headers, "X-Client-Request-Id": request_id}
        for attempt_index in range(attempts):
            response: httpx.Response | None = None
            cause: httpx.TransportError | None = None
            fallback_delay = min(60.0, 2.0**attempt_index)
            jitter = random.uniform(0.0, self.settings.ai_transient_retry_jitter_seconds)
            transport_delay = fallback_delay + jitter
            response_delay: float | None = None

            def cooldown_for_response(
                candidate: httpx.Response,
                fallback: float = fallback_delay,
                jitter_seconds: float = jitter,
            ) -> float | None:
                nonlocal response_delay
                error_type, error_code, _ = self._error_metadata(candidate)
                if not self._is_retryable_response(candidate, error_type, error_code):
                    return None
                retry_after = self._retry_after_seconds(candidate)
                response_delay = (
                    retry_after if retry_after is not None else fallback
                ) + jitter_seconds
                return response_delay

            try:
                response = await self._request_gate.request(
                    lambda: self.client.post(
                        url,
                        headers=request_headers,
                        json=payload,
                    ),
                    cooldown_for_response=cooldown_for_response,
                    transport_cooldown_seconds=transport_delay,
                )
            except httpx.TransportError as error:
                cause = error
                error_type = None
                error_code = None
                detail = str(error)
                delay = transport_delay
            else:
                if response.status_code < 400:
                    return response
                error_type, error_code, detail = self._error_metadata(response)
                if not self._is_retryable_response(response, error_type, error_code):
                    raise AIProviderRequestError(
                        "OpenAI request failed with a non-retryable response: "
                        f"HTTP {response.status_code}, code={error_code or 'unknown'}; {detail}",
                        status_code=response.status_code,
                        error_code=error_code,
                    )
                assert response_delay is not None
                delay = response_delay

            attempts_exhausted = attempt_index + 1 >= attempts
            elapsed = loop.time() - started
            deadline_exhausted = elapsed + delay > max_elapsed
            status_code = response.status_code if response is not None else None
            if attempts_exhausted or deadline_exhausted:
                reason = (
                    "attempt limit reached" if attempts_exhausted else "retry window exhausted"
                )
                raise AIProviderRequestError(
                    "OpenAI request remained temporarily unavailable: "
                    f"{reason}; HTTP {status_code or 'transport'}, "
                    f"code={error_code or 'unknown'}; {detail}",
                    status_code=status_code,
                    error_code=error_code,
                    retryable=True,
                ) from cause

            logger.warning(
                "OpenAI request temporarily unavailable; retrying in %.3fs "
                "(attempt %d/%d, status=%s, code=%s)",
                delay,
                attempt_index + 1,
                attempts,
                status_code or "transport",
                error_code or "unknown",
                extra={
                    "attempt": attempt_index + 1,
                    "delay_seconds": round(delay, 3),
                    "status_code": status_code,
                    "error_type": error_type,
                    "error_code": error_code,
                    "openai_request_id": response.headers.get("x-request-id")
                    if response is not None
                    else None,
                    "client_request_id": request_id,
                },
            )

        raise AssertionError("OpenAI retry loop ended unexpectedly")

    async def _generate(
        self,
        prompt: str,
        *,
        json_output: bool = False,
        response_schema: type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        if self.settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

        payload: dict[str, object] = {
            "model": self.model,
            "input": prompt,
            "reasoning": {"effort": self.settings.openai_reasoning_effort},
            "store": False,
        }
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        if response_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": response_schema.__name__.lower()[:64],
                    "schema": _openai_json_schema(response_schema.model_json_schema()),
                    "strict": True,
                }
            }
        elif json_output:
            payload["text"] = {"format": {"type": "json_object"}}

        response = await self._post_with_retry(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": (f"Bearer {self.settings.openai_api_key.get_secret_value()}"),
                "Content-Type": "application/json",
            },
            payload=payload,
        )

        body = response.json()
        usage = body.get("usage", {})
        if isinstance(usage, dict):
            await self._record_token_usage(
                usage.get("input_tokens"),
                usage.get("output_tokens"),
                usage.get("total_tokens"),
            )
        status = body.get("status")
        if status != "completed":
            detail = body.get("incomplete_details") or body.get("error") or status
            if isinstance(detail, dict) and detail.get("reason") == "content_filter":
                raise AIProviderSafetyRefusalError("OpenAI", detail["reason"])
            raise RuntimeError(f"OpenAI generation did not complete: {detail}")

        generated_parts: list[str] = []
        for output in body.get("output", []):
            if output.get("type") != "message":
                continue
            for content in output.get("content", []):
                if content.get("type") == "refusal":
                    raise AIProviderSafetyRefusalError(
                        "OpenAI", content.get("refusal", "reason was not provided")
                    )
                if content.get("type") == "output_text":
                    generated_parts.append(content.get("text", ""))
        generated_text = "".join(generated_parts).strip()
        if not generated_text:
            raise RuntimeError("OpenAI returned an empty response")
        return generated_text


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


def _prompt_with_rejection(
    prompt: str,
    error: Exception,
    attempted_output: str | None = None,
) -> str:
    feedback = (
        "\n\n前回の出力は次の理由で受理できませんでした。同じ誤りを繰り返さず、"
        "全体を正しいJSONとして再生成してください:\n"
        + str(error)[:2_000]
    )
    if attempted_output:
        feedback += "\n\n受理されなかった前回出力:\n```json\n"
        feedback += attempted_output[:12_000]
        feedback += "\n```"
    return prompt + feedback


def _generated_artifact_failure_feedback(error: Exception) -> str:
    if not isinstance(error, _GeneratedArtifactValidationFailure):
        return str(error)
    return json.dumps(
        {
            "kind": f"{error.artifact_kind}_validation_failure",
            "validation_error": error.validation_error[:4_000],
            "attempted_output": error.attempted_output,
        },
        ensure_ascii=False,
    )


def _compact_scenario_review(review: ScenarioReview) -> dict:
    findings = []
    for finding in review.findings[:8]:
        findings.append(
            {
                "step_id": finding.step_id,
                "severity": finding.severity,
                "category": finding.category,
                "repair_target": finding.repair_target,
                "repair_fields": finding.repair_fields,
                "evidence": finding.evidence[:500],
                "remediation": finding.remediation[:500],
            }
        )
    return {
        "summary": review.summary[:1_000],
        "findings": findings,
        "omitted_findings": max(0, len(review.findings) - len(findings)),
    }
