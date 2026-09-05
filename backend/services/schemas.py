"""The shape of what the model is allowed to say.

FileReview.model_json_schema() is passed to Ollama as the `format`, so the
model can only emit these fields with these enum values. Validation here is
the second line; the third is post-processing against the diff itself."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    ACCESSIBILITY = "accessibility"


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
    # Field order is the order the model writes the keys in: with every key required, Ollama's grammar
    # holds the model to this sequence (measured 2026-09-05: 182 of 182 replies followed it). The summary
    # comes first on purpose. Writing one sentence on what the change does before listing findings acts
    # as a scratchpad for a 9B model: with findings first, the same prompt on the same 91 diffs went from
    # recall 0.92 to 0.87 while its summaries still described the problems it then failed to list.
    # Both keys are required, not defaulted: an optional key is one the grammar lets the model skip, and
    # a 9B model did exactly that when an unescaped quote in the summary (`role="button"`) ended the
    # string early, so every HTML finding it had was never written.
    summary: str = Field(max_length=500)
    findings: List[Finding] = Field(max_length=20)


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


class CrossVerdict(Verdict):
    """One verdict from the cross-examiner about the first reviewer's numbered finding."""
    index: int = Field(ge=0)


class CrossExamination(BaseModel):
    """The cross-examiner's whole answer for one file: a verdict per numbered
    finding, the findings it believes were missed, and a note on where it
    disagrees. Additions are plain Findings and go through the same
    postprocess as the first reviewer's."""
    # all three required for the same reason as FileReview.findings: an optional key is a key the
    # grammar lets the model skip, and a skipped verdicts list reads as "nothing to say"
    verdicts: List[CrossVerdict] = Field(max_length=20)
    additions: List[Finding] = Field(max_length=10)
    summary_note: str = Field(max_length=300)


class ReviewedFinding(Finding):
    """A finding with provenance. Never part of the grammar handed to the
    model: these fields are stamped by the pipeline, not invented by it."""
    source_model: str = ""
    cross_verdict: Optional[str] = None   # real, false_positive, or None when not examined
    cross_reason: str = ""
    cross_severity: Optional[Severity] = None


class AnnotatedFileReview(BaseModel):
    findings: List[ReviewedFinding] = Field(default_factory=list)
    summary: str = Field(default="", max_length=500)


def output_schema() -> dict:
    """JSON schema handed to Ollama's `format` parameter."""
    return FileReview.model_json_schema()


def verdict_schema() -> dict:
    return Verdict.model_json_schema()


def cross_schema() -> dict:
    return CrossExamination.model_json_schema()
