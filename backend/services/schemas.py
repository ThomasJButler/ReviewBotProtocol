"""The shape of what the model is allowed to say.

FileReview.model_json_schema() is passed to Ollama as the `format`, so the
model can only emit these fields with these enum values. Validation here is
the second line; the third is post-processing against the diff itself."""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class Category(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}


class Finding(BaseModel):
    category: Category
    severity: Severity
    title: str = Field(max_length=120)
    line: int = Field(ge=1, description="Line number in the new version of the file")
    evidence: str = Field(max_length=300, description="The exact line of code the finding is about, quoted")
    recommendation: str = Field(max_length=600)
    confidence: float = Field(ge=0.0, le=1.0)


class FileReview(BaseModel):
    findings: List[Finding] = Field(default_factory=list, max_length=20)
    summary: str = Field(max_length=500)


class VerdictLabel(str, Enum):
    REAL = "real"
    FALSE_POSITIVE = "false_positive"


class Verdict(BaseModel):
    """The verifier's answer about one candidate finding. A named label
    rather than a boolean, because a small model asked to "confirm" while
    "trying to disprove" answers the wrong question."""
    verdict: VerdictLabel
    severity: Severity
    reason: str = Field(max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def confirmed(self) -> bool:
        return self.verdict == VerdictLabel.REAL


def output_schema() -> dict:
    """JSON schema handed to Ollama's `format` parameter."""
    return FileReview.model_json_schema()


def verdict_schema() -> dict:
    return Verdict.model_json_schema()
