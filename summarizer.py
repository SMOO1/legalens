"""
LegalLens — Agent 3: The Summarizer
======================================
Responsibility: Two jobs in one agent:

1. SUMMARY MODE: Takes all analyzed clauses and synthesizes them into
   a clean executive summary — what the document is, top 3 risks,
   overall risk score, and a plain one-sentence bottom line.

2. Q&A MODE: Answers user follow-up questions using RAG-retrieved
   chunks from the FAISS vector store. Runs on Groq (Llama 3.3 70B)
   for speed — the Q&A interface needs to feel instant.

This agent is the user-facing layer. It speaks plain English only.
"""

import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from .state import AgentState, AnalyzedClause


# ── Summary Mode ────────────────────────────────────────────────────────────

SUMMARIZER_SYSTEM_PROMPT = """You are a legal document summarizer. Your job is to take a list of
analyzed legal clauses and produce a clear, honest executive summary for someone who is NOT a lawyer.

You will output a JSON object with these exact fields:
- "executive_summary": A 3-5 sentence plain-English overview of the document and its key themes.
  Do not use legal jargon. Write like you're explaining to a smart friend.
- "top_risks": An array of EXACTLY 3 strings. Each string is one key risk in plain English,
  starting with the severity level. Example: "HIGH: You permanently waive your right to sue..."
- "bottom_line": A single sentence verdict. Should start with one of:
  "Sign with caution —", "Do not sign without a lawyer —", "This is a fairly standard contract —",
  or "Seek legal advice before signing —"
- "overall_risk_score": One of "LOW", "MEDIUM", "HIGH", or "CRITICAL"
  (CRITICAL means multiple HIGH severity clauses that compound each other)

Rules:
- Be direct and honest. If the contract is bad for the signer, say so clearly.
- Prioritize HIGH severity clauses in your top_risks.
- The executive_summary should mention the document type and what it governs.
- Never use the words "herein", "whereas", "party of the first part", or any legalese.

Output ONLY a valid JSON object. No preamble, no markdown fences.
"""

SUMMARIZER_USER_PROMPT = """Here is the full analysis of "{document_name}" ({document_type}):

Total clauses found: {total_clauses}
HIGH severity: {high_count}
MEDIUM severity: {med_count}  
LOW severity: {low_count}

ANALYZED CLAUSES (sorted by severity):
{analyzed_clauses_json}

Generate the executive summary JSON object now.
"""


# ── Q&A Mode ────────────────────────────────────────────────────────────────

QA_SYSTEM_PROMPT = """You are a legal document assistant. A user has uploaded a legal document
and is asking questions about it.

You have access to relevant excerpts from the document (retrieved by semantic search).
Answer the user's question based ONLY on the document content provided.

Rules:
- Answer in plain English, no jargon.
- If the document doesn't address the question, say so clearly: "This document doesn't appear to address that."
- Be specific — quote or reference the relevant part of the document when applicable.
- Keep answers concise: 2-4 sentences unless the question requires more detail.
- Never make up information not present in the retrieved excerpts.
- If the answer has legal implications, note that the user should consult a lawyer for advice.
"""

QA_USER_PROMPT = """DOCUMENT: {document_name}

RELEVANT EXCERPTS FROM THE DOCUMENT:
{retrieved_chunks}

USER QUESTION: {question}

Answer based only on the document excerpts above.
"""


def summarizer_agent(state: AgentState) -> AgentState:
    """
    Agent 3 (Summary Mode): Synthesizes analyzed clauses into an executive summary.

    Reads: analyzed_clauses, document_name, document_type
    Writes: executive_summary, top_risks, bottom_line, overall_risk_score
    """
    print("📝 [Summarizer Agent] Generating executive summary...")

    analyzed_clauses = state.get("analyzed_clauses", [])

    if not analyzed_clauses:
        print("  ⚠️  No analyzed clauses to summarize.")
        return {
            **state,
            "executive_summary": "No clauses could be extracted from this document.",
            "top_risks": ["Unable to analyze document — no clauses found."],
            "bottom_line": "Sign with caution — this document could not be fully analyzed.",
            "overall_risk_score": "MEDIUM",
            "current_agent": "summarizer",
        }

    high_count = sum(1 for c in analyzed_clauses if c["severity"] == "HIGH")
    med_count = sum(1 for c in analyzed_clauses if c["severity"] == "MEDIUM")
    low_count = sum(1 for c in analyzed_clauses if c["severity"] == "LOW")

    # Use Gemini for the summary — it produces better long-form prose
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,
        max_tokens=2048,
    )

    system_prompt = SUMMARIZER_SYSTEM_PROMPT

    user_prompt = SUMMARIZER_USER_PROMPT.format(
        document_name=state["document_name"],
        document_type=state["document_type"],
        total_clauses=len(analyzed_clauses),
        high_count=high_count,
        med_count=med_count,
        low_count=low_count,
        analyzed_clauses_json=json.dumps(analyzed_clauses, indent=2)[:20000],
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        raw_output = response.content.strip()
        raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
        raw_output = re.sub(r"\s*```$", "", raw_output)

        summary_data = json.loads(raw_output)

        print(f"  ✅ Summary generated. Overall risk: {summary_data.get('overall_risk_score', 'UNKNOWN')}")

        return {
            **state,
            "executive_summary": summary_data.get("executive_summary", ""),
            "top_risks": summary_data.get("top_risks", []),
            "bottom_line": summary_data.get("bottom_line", ""),
            "overall_risk_score": summary_data.get("overall_risk_score", "MEDIUM"),
            "current_agent": "summarizer",
        }

    except json.JSONDecodeError as e:
        error_msg = f"Summarizer JSON parse error: {e}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "executive_summary": "Summary generation failed — please review clauses manually.",
            "top_risks": [f"HIGH: {c['type']} — {c['severity_reason']}" for c in analyzed_clauses[:3] if c["severity"] == "HIGH"],
            "bottom_line": "Sign with caution — automated summary failed, review clauses manually.",
            "overall_risk_score": "HIGH" if high_count > 0 else "MEDIUM",
            "current_agent": "summarizer",
            "errors": state.get("errors", []) + [error_msg],
        }
    except Exception as e:
        error_msg = f"Summarizer agent failed: {e}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "executive_summary": "",
            "top_risks": [],
            "bottom_line": "",
            "overall_risk_score": "MEDIUM",
            "current_agent": "summarizer",
            "errors": state.get("errors", []) + [error_msg],
        }


def qa_agent(state: AgentState) -> AgentState:
    """
    Agent 3 (Q&A Mode): Answers user questions using RAG-retrieved chunks.

    Runs on Groq + Llama 3.3 70B for low latency.

    Reads: qa_question, retrieved_chunks, document_name
    Writes: qa_answer
    """
    print("💬 [Q&A Agent] Answering user question...")

    question = state.get("qa_question", "")
    retrieved_chunks = state.get("retrieved_chunks", [])

    if not question:
        return {**state, "qa_answer": "No question provided.", "current_agent": "qa"}

    if not retrieved_chunks:
        return {
            **state,
            "qa_answer": "I couldn't find relevant sections in the document to answer your question. Try rephrasing.",
            "current_agent": "qa",
        }

    # Groq for speed — Q&A needs to feel real-time
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=1024,
    )

    chunks_text = "\n\n---\n\n".join(retrieved_chunks)

    user_prompt = QA_USER_PROMPT.format(
        document_name=state["document_name"],
        retrieved_chunks=chunks_text[:8000],  # Cap context
        question=question,
    )

    try:
        response = llm.invoke([
            SystemMessage(content=QA_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        answer = response.content.strip()
        print(f"  ✅ Q&A answer generated ({len(answer)} chars)")

        return {
            **state,
            "qa_answer": answer,
            "current_agent": "qa",
        }

    except Exception as e:
        error_msg = f"Q&A agent failed: {e}"
        print(f"  ❌ {error_msg}")
        return {
            **state,
            "qa_answer": "Sorry, I encountered an error answering your question. Please try again.",
            "current_agent": "qa",
            "errors": state.get("errors", []) + [error_msg],
        }
