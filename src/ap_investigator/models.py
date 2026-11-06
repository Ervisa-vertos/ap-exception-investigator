"""Structured outputs exchanged between workflow steps."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .domain import NextStep, RootCause


class Evidence(BaseModel):
    record_id: str = Field(description="ID of a record a tool returned to you (invoice, PO, receipt, vendor, change-log or message ID), copied exactly")
    fact: str = Field(description="The specific fact from that record, with numbers")


class Citation(BaseModel):
    policy_section: str = Field(description="Exact section ID returned by search_policy, e.g. 'AP-POL-01 §2.2'")
    quote: str = Field(description="Short quote (max ~25 words) from that section supporting the claim")


class ProposedAction(BaseModel):
    action: Literal["release_hold", "request_credit_note"]
    amount: float | None = Field(description="Credit note amount, or null")
    justification: str


class Investigation(BaseModel):
    invoice_id: str
    on_hold: bool
    root_causes: list[RootCause] = Field(description="All causes found, most important first")
    summary: str = Field(description="2-4 sentences in plain language for an AP clerk")
    evidence: list[Evidence]
    citations: list[Citation]
    next_steps: list[NextStep] = Field(description="Recommended next steps, most important first")
    next_steps_explained: str
    # No defaults on purpose: OpenAI strict JSON-schema mode needs every field required (nullable is fine).
    proposed_action: ProposedAction | None = Field(
        description="Only if the user asked for an action; it is NEVER executed without the gate and a human. Else null")
    confidence: Literal["high", "medium", "low"]


class ReviewIssue(BaseModel):
    kind: Literal[
        "evidence_not_retrieved", "citation_not_retrieved", "unknown_citation", "missing_citation",
        "unsupported_root_cause", "missed_critical_cause", "forbidden_next_step", "priority_violation",
        "unacceptable_next_step", "quote_not_in_section", "action_from_untrusted_text", "unsupported_statement", "malformed_output",
    ]
    detail: str


class Review(BaseModel):
    approved: bool
    issues: list[ReviewIssue]


class ActionRequest(BaseModel):
    action: Literal["release_hold", "request_credit_note"]
    invoice_id: str
    amount: float | None = None
    justification: str


class ActionResult(BaseModel):
    action: str
    invoice_id: str
    executed: bool
    reason: str
    approved_by: str | None = None


class Outcome(BaseModel):
    """What the workflow returns to the caller (CLI, API, UI, evals)."""
    status: Literal["answered", "needs_human_review", "refused", "error", "clarify"]
    question: str
    message: str
    investigation: Investigation | None = None
    review: Review | None = None
    review_rounds: int = 0
    action_request: ActionRequest | None = None
    records_retrieved: list[str] = Field(default_factory=list)
    policy_sections_retrieved: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    injection_flags: list[str] = Field(default_factory=list)
