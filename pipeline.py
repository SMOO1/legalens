"""
LegalLens — LangGraph Pipeline
================================
This is the orchestration layer. It wires all 3 agents into a
directed graph with proper sequencing and error handling.

Pipeline flow:
  START → extractor → analyst → summarizer → END
                                     ↑
  (Q&A is a separate sub-graph invoked independently)

Usage:
  from agents.pipeline import run_analysis, run_qa

  # Full document analysis
  result = await run_analysis(
      document_text="...",
      document_name="my_contract.pdf",
      document_type="Employment Contract"
  )

  # Q&A on an already-analyzed document
  answer = await run_qa(
      state=result,
      question="Can they use my photo commercially?",
      retrieved_chunks=["Section 4: The company may use..."]
  )
"""

from langgraph.graph import StateGraph, END
from .state import AgentState
from .extractor import extractor_agent
from .analyst import analyst_agent
from .summarizer import summarizer_agent, qa_agent


# ── Helper: decide if we should continue after extractor ────────────────────

def should_continue_after_extraction(state: AgentState) -> str:
    """
    Edge condition: if the extractor found no clauses (e.g. document was
    unreadable or too short), skip to summarizer directly.
    """
    clauses = state.get("clauses", [])
    if not clauses:
        print("  ⚠️  No clauses extracted — skipping analyst, going straight to summarizer.")
        return "summarizer"
    return "analyst"


# ── Build the main analysis graph ───────────────────────────────────────────

def build_analysis_graph() -> StateGraph:
    """
    Constructs the LangGraph StateGraph for full document analysis.

    Graph:
      extractor ──(clauses found)──→ analyst ──→ summarizer
               ╰──(no clauses)──────────────────→ summarizer
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("extractor", extractor_agent)
    graph.add_node("analyst", analyst_agent)
    graph.add_node("summarizer", summarizer_agent)

    # Entry point
    graph.set_entry_point("extractor")

    # Conditional edge: skip analyst if no clauses found
    graph.add_conditional_edges(
        "extractor",
        should_continue_after_extraction,
        {
            "analyst": "analyst",
            "summarizer": "summarizer",
        }
    )

    # Analyst always goes to summarizer
    graph.add_edge("analyst", "summarizer")

    # Summarizer is the terminal node
    graph.add_edge("summarizer", END)

    return graph.compile()


# ── Build the Q&A sub-graph ─────────────────────────────────────────────────

def build_qa_graph() -> StateGraph:
    """
    Constructs the Q&A sub-graph. Much simpler — just one node.
    Invoked independently from the main analysis graph.
    """
    graph = StateGraph(AgentState)
    graph.add_node("qa", qa_agent)
    graph.set_entry_point("qa")
    graph.add_edge("qa", END)
    return graph.compile()


# ── Compiled graph singletons (built once, reused per request) ──────────────
_analysis_graph = None
_qa_graph = None


def get_analysis_graph():
    global _analysis_graph
    if _analysis_graph is None:
        _analysis_graph = build_analysis_graph()
    return _analysis_graph


def get_qa_graph():
    global _qa_graph
    if _qa_graph is None:
        _qa_graph = build_qa_graph()
    return _qa_graph


# ── Public API ───────────────────────────────────────────────────────────────

async def run_analysis(
    document_text: str,
    document_name: str,
    document_type: str = "Legal Contract",
) -> AgentState:
    """
    Run the full 3-agent analysis pipeline on a document.

    Args:
        document_text: Raw extracted text from the PDF/DOCX
        document_name: Original filename (shown to user)
        document_type: Type of contract (auto-detected or user-specified)

    Returns:
        Final AgentState with all fields populated:
        - clauses: raw extracted clauses
        - analyzed_clauses: risk-scored clauses
        - executive_summary, top_risks, bottom_line, overall_risk_score
    """
    graph = get_analysis_graph()

    initial_state: AgentState = {
        "document_text": document_text,
        "document_name": document_name,
        "document_type": document_type,
        "clauses": [],
        "analyzed_clauses": [],
        "executive_summary": None,
        "top_risks": None,
        "bottom_line": None,
        "overall_risk_score": None,
        "retrieved_chunks": [],
        "qa_question": None,
        "qa_answer": None,
        "errors": [],
        "current_agent": None,
    }

    print(f"\n🚀 LegalLens pipeline starting for: {document_name}")
    print("=" * 60)

    final_state = await graph.ainvoke(initial_state)

    print("=" * 60)
    print(f"✅ Pipeline complete. Overall risk: {final_state.get('overall_risk_score')}")
    print(f"   Clauses found: {len(final_state.get('clauses', []))}")
    print(f"   Errors: {len(final_state.get('errors', []))}")

    return final_state


async def run_qa(
    state: AgentState,
    question: str,
    retrieved_chunks: list[str],
) -> str:
    """
    Run the Q&A agent on a user question.

    Args:
        state: The AgentState from a previous run_analysis call
        question: The user's plain-English question
        retrieved_chunks: Relevant chunks from FAISS retrieval

    Returns:
        A plain-English answer string
    """
    graph = get_qa_graph()

    qa_state: AgentState = {
        **state,
        "qa_question": question,
        "retrieved_chunks": retrieved_chunks,
        "qa_answer": None,
    }

    result = await graph.ainvoke(qa_state)
    return result.get("qa_answer", "Unable to generate an answer.")
