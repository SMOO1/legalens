"""
LegalLens — Shared Agent State
================================
This is the single state object that flows through the entire
LangGraph pipeline. Every agent reads from and writes to this state.
Think of it as the "baton" being passed between agents.
"""

from typing import TypedDict, Annotated, Optional
import operator


class Clause(TypedDict):
    """A single clause extracted from the document."""
    id: str                    # e.g. "clause_001"
    type: str                  # e.g. "Non-Compete", "Liability Waiver"
    raw_text: str              # The exact text from the document
    location: str              # e.g. "Section 4, Paragraph 2"


class AnalyzedClause(TypedDict):
    """A clause after the Analyst agent has processed it."""
    id: str
    type: str
    raw_text: str
    location: str
    severity: str              # "LOW", "MEDIUM", "HIGH"
    severity_reason: str       # Plain-English explanation of why it's flagged
    plain_english: str         # What this clause actually means
    baseline_comparison: str   # How it compares to standard contracts
    negotiation_tip: str       # What the user could push back on


class AgentState(TypedDict):
    """
    The full pipeline state. Flows through:
      Extractor → Analyst → Summarizer
    """
    # ── Input ──────────────────────────────────────────────────────────────
    document_text: str                          # Raw extracted document text
    document_name: str                          # Original filename
    document_type: str                          # e.g. "NDA", "Lease", "Employment Contract"

    # ── Extractor Output ───────────────────────────────────────────────────
    clauses: Annotated[list[Clause], operator.add]   # Raw extracted clauses

    # ── Analyst Output ─────────────────────────────────────────────────────
    analyzed_clauses: Annotated[list[AnalyzedClause], operator.add]

    # ── Summarizer Output ──────────────────────────────────────────────────
    executive_summary: Optional[str]            # One-page summary for the user
    top_risks: Optional[list[str]]              # Top 3 risks in plain English
    bottom_line: Optional[str]                  # One-sentence verdict
    overall_risk_score: Optional[str]           # "LOW", "MEDIUM", "HIGH", "CRITICAL"

    # ── RAG Context (for Q&A) ──────────────────────────────────────────────
    retrieved_chunks: Annotated[list[str], operator.add]  # Chunks from FAISS retrieval
    qa_question: Optional[str]                  # User's follow-up question
    qa_answer: Optional[str]                    # Summarizer's answer

    # ── Pipeline Metadata ──────────────────────────────────────────────────
    errors: Annotated[list[str], operator.add]  # Any errors encountered
    current_agent: Optional[str]                # Which agent is currently running
