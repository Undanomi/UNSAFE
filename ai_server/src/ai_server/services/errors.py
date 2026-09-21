from __future__ import annotations


class ScenarioInputRevisionRequiredError(RuntimeError):
    """The requested scenario constraints remain infeasible after semantic review."""

    code = "scenario_input_revision_required"

    def __init__(self, summary: str, findings: list[dict]) -> None:
        self.summary = summary
        self.findings = findings
        super().__init__(summary)

    def event_data(self) -> dict:
        return {
            "code": self.code,
            "message": "現在の問題設定では成立するシナリオを生成できませんでした。",
            "summary": self.summary,
            "findings": self.findings,
        }


def exception_detail(error: BaseException) -> str:
    """Return a useful persisted message, including for exceptions with empty str()."""
    name = type(error).__name__
    message = str(error).strip()
    return f"{name}: {message}" if message else name
