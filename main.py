"""
LegalLens — main.py
====================
Self-contained FastAPI backend. All agents are inlined here so
there are zero import path issues regardless of how you run it.

Run with:
    uvicorn main:app --reload

Or just:
    python main.py
"""

import asyncio
import io
import json
import os
import re
import uuid
from typing import Annotated, AsyncGenerator, Optional, TypedDict
import operator

import PyPDF2
import docx as python_docx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

load_dotenv()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════════

class Clause(TypedDict):
    id: str
    type: str
    raw_text: str
    location: str

class AnalyzedClause(TypedDict):
    id: str
    type: str
    raw_text: str
    location: str
    severity: str
    severity_reason: str
    plain_english: str
    baseline_comparison: str
    negotiation_tip: str

class AgentState(TypedDict):
    document_text: str
    document_name: str
    document_type: str
    clauses: Annotated[list[Clause], operator.add]
    analyzed_clauses: Annotated[list[AnalyzedClause], operator.add]
    executive_summary: Optional[str]
    top_risks: Optional[list[str]]
    bottom_line: Optional[str]
    overall_risk_score: Optional[str]
    retrieved_chunks: Annotated[list[str], operator.add]
    qa_question: Optional[str]
    qa_answer: Optional[str]
    errors: Annotated[list[str], operator.add]
    current_agent: Optional[str]


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════════════

CLAUSE_TYPES = [
    "Liability Waiver", "IP Assignment", "Non-Compete", "Arbitration",
    "Auto-Renewal", "Data & Privacy", "Termination for Cause",
    "Indemnification", "Force Majeure", "Governing Law",
    "Amendment / Unilateral Change", "Photo & Media Rights",
    "Confidentiality / NDA", "Payment Terms", "Limitation of Liability",
    "Warranty Disclaimer",
]

EXTRACTOR_SYSTEM = """You are a legal clause extraction engine.
Find every legal clause in the document. Output ONLY a valid JSON array.
Each object must have: id (string like "clause_001"), type (from list), raw_text (verbatim), location (e.g. "Section 3").
Clause types to find: {clause_types}
No explanation, no markdown fences. Raw JSON array only."""

EXTRACTOR_USER = """Document: {document_name} ({document_type})

--- START ---
{document_text}
--- END ---

Extract all clauses as a JSON array."""

def extractor_agent(state: AgentState) -> AgentState:
    print("Extractor: Scanning for clauses...")
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1, max_tokens=8192)
    try:
        response = llm.invoke([
            SystemMessage(content=EXTRACTOR_SYSTEM.format(clause_types=", ".join(CLAUSE_TYPES))),
            HumanMessage(content=EXTRACTOR_USER.format(
                document_name=state["document_name"],
                document_type=state["document_type"],
                document_text=state["document_text"][:50000],
            )),
        ])
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.content.strip())
        clauses = [
            Clause(id=c["id"], type=c["type"], raw_text=c["raw_text"], location=c["location"])
            for c in json.loads(raw)
            if all(k in c for k in ["id", "type", "raw_text", "location"])
        ]
        print(f"  Found {len(clauses)} clauses")
        return {**state, "clauses": clauses, "current_agent": "extractor", "errors": []}
    except Exception as e:
        print(f"  Extractor error: {e}")
        return {**state, "clauses": [], "current_agent": "extractor", "errors": [str(e)]}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 2 — ANALYST
# ═══════════════════════════════════════════════════════════════════════════════

BASELINES = """
- Non-Compete: Standard = 6-12 months, limited geography. Over 2 years or nationwide = aggressive.
- IP Assignment: Standard = work done on company time. Assigning ALL inventions = predatory.
- Arbitration: Standard includes right to appeal. Mandatory binding with no class action = aggressive.
- Liability Waiver: Standard limits ordinary negligence. Waiving gross negligence = risky.
- Auto-Renewal: Standard = 30-day notice to cancel. Under 7 days = aggressive.
- Data & Privacy: Standard limits sharing to service providers. Selling data = red flag.
- Indemnification: Standard = mutual. One-sided = red flag.
- Photo & Media Rights: Standard = explicit consent per use. Blanket lifetime rights = aggressive.
"""

ANALYST_SYSTEM = """You are a senior legal analyst. Analyze each clause provided.
For each, output a JSON object with ALL these fields:
- id, type, raw_text, location (same as input)
- severity: "LOW", "MEDIUM", or "HIGH"
- severity_reason: 1-2 sentences why (plain English)
- plain_english: what this actually means for the person signing
- baseline_comparison: how it compares to standard practice
- negotiation_tip: specific actionable pushback advice

Severity: HIGH = significant risk. MEDIUM = unusual/restrictive. LOW = standard/normal.
Baselines: {baselines}
Output ONLY a valid JSON array. No markdown."""

ANALYST_USER = """Analyze these {count} clauses from a {document_type} called "{document_name}":
{clauses_json}
Return a JSON array with one fully analyzed object per clause."""

def analyst_agent(state: AgentState) -> AgentState:
    print("Analyst: Scoring clause risk...")
    clauses = state.get("clauses", [])
    if not clauses:
        return {**state, "analyzed_clauses": [], "current_agent": "analyst", "errors": ["No clauses to analyze"]}

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2, max_tokens=8192)
    all_analyzed = []
    BATCH = 8

    for i in range(0, len(clauses), BATCH):
        batch = clauses[i:i + BATCH]
        print(f"  Batch {i//BATCH + 1}/{(len(clauses)+BATCH-1)//BATCH}")
        try:
            response = llm.invoke([
                SystemMessage(content=ANALYST_SYSTEM.format(baselines=BASELINES)),
                HumanMessage(content=ANALYST_USER.format(
                    count=len(batch),
                    document_type=state["document_type"],
                    document_name=state["document_name"],
                    clauses_json=json.dumps(batch, indent=2),
                )),
            ])
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.content.strip())
            required = ["id","type","raw_text","location","severity","severity_reason","plain_english","baseline_comparison","negotiation_tip"]
            for item in json.loads(raw):
                if all(k in item for k in required):
                    all_analyzed.append(AnalyzedClause(**{k: item[k] for k in required}))
        except Exception as e:
            print(f"  Analyst batch error: {e}")

    all_analyzed.sort(key=lambda c: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(c["severity"], 3))
    print(f"  Done — HIGH: {sum(1 for c in all_analyzed if c['severity']=='HIGH')}  MEDIUM: {sum(1 for c in all_analyzed if c['severity']=='MEDIUM')}  LOW: {sum(1 for c in all_analyzed if c['severity']=='LOW')}")
    return {**state, "analyzed_clauses": all_analyzed, "current_agent": "analyst"}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 3 — SUMMARIZER + Q&A
# ═══════════════════════════════════════════════════════════════════════════════

SUMMARIZER_SYSTEM = """You are a legal document summarizer. Write for non-lawyers only.
Output a JSON object with these exact fields:
- executive_summary: 3-5 sentence plain-English overview (no jargon)
- top_risks: array of EXACTLY 3 strings, each starting with severity e.g. "HIGH: You waive..."
- bottom_line: one sentence starting with one of: "Sign with caution —", "Do not sign without a lawyer —", "This is a fairly standard contract —", "Seek legal advice before signing —"
- overall_risk_score: "LOW", "MEDIUM", "HIGH", or "CRITICAL"
Be direct. No legalese. Raw JSON only."""

SUMMARIZER_USER = """Document: "{document_name}" ({document_type})
Clauses: {total} total — {high} HIGH, {med} MEDIUM, {low} LOW

{clauses_json}

Generate the executive summary JSON."""

QA_SYSTEM = """You are a legal document assistant. Answer questions using ONLY the provided excerpts.
Plain English only, 2-4 sentences. If the document doesn't address it, say so clearly.
Never make up information not in the excerpts."""

QA_USER = """Document: {document_name}

Excerpts:
{chunks}

Question: {question}"""

def summarizer_agent(state: AgentState) -> AgentState:
    print("Summarizer: Generating executive summary...")
    analyzed = state.get("analyzed_clauses", [])
    high = sum(1 for c in analyzed if c["severity"] == "HIGH")
    med  = sum(1 for c in analyzed if c["severity"] == "MEDIUM")
    low  = sum(1 for c in analyzed if c["severity"] == "LOW")

    if not analyzed:
        return {
            **state,
            "executive_summary": "No clauses could be extracted from this document.",
            "top_risks": ["Unable to analyze — no clauses found."],
            "bottom_line": "Sign with caution — document could not be fully analyzed.",
            "overall_risk_score": "MEDIUM",
            "current_agent": "summarizer",
        }

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3, max_tokens=2048)
    try:
        response = llm.invoke([
            SystemMessage(content=SUMMARIZER_SYSTEM),
            HumanMessage(content=SUMMARIZER_USER.format(
                document_name=state["document_name"],
                document_type=state["document_type"],
                total=len(analyzed), high=high, med=med, low=low,
                clauses_json=json.dumps(analyzed, indent=2)[:20000],
            )),
        ])
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.content.strip())
        data = json.loads(raw)
        print(f"  Done. Overall risk: {data.get('overall_risk_score')}")
        return {
            **state,
            "executive_summary": data.get("executive_summary", ""),
            "top_risks": data.get("top_risks", []),
            "bottom_line": data.get("bottom_line", ""),
            "overall_risk_score": data.get("overall_risk_score", "MEDIUM"),
            "current_agent": "summarizer",
        }
    except Exception as e:
        print(f"  Summarizer error: {e}")
        return {
            **state,
            "executive_summary": "Summary generation failed.",
            "top_risks": [f"HIGH: {c['type']} — {c['severity_reason']}" for c in analyzed[:3] if c["severity"] == "HIGH"],
            "bottom_line": "Sign with caution — review clauses manually.",
            "overall_risk_score": "HIGH" if high > 0 else "MEDIUM",
            "current_agent": "summarizer",
            "errors": state.get("errors", []) + [str(e)],
        }

def qa_agent(state: AgentState) -> AgentState:
    print("Q&A: Answering question...")
    question = state.get("qa_question", "")
    chunks = state.get("retrieved_chunks", [])
    if not question:
        return {**state, "qa_answer": "No question provided.", "current_agent": "qa"}
    if not chunks:
        return {**state, "qa_answer": "No relevant sections found. Try rephrasing.", "current_agent": "qa"}

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, max_tokens=1024)
    try:
        response = llm.invoke([
            SystemMessage(content=QA_SYSTEM),
            HumanMessage(content=QA_USER.format(
                document_name=state["document_name"],
                chunks="\n\n---\n\n".join(chunks)[:8000],
                question=question,
            )),
        ])
        return {**state, "qa_answer": response.content.strip(), "current_agent": "qa"}
    except Exception as e:
        print(f"  Q&A error: {e}")
        return {**state, "qa_answer": "Error answering question. Please try again.", "current_agent": "qa", "errors": state.get("errors", []) + [str(e)]}


# ═══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def route_after_extraction(state: AgentState) -> str:
    return "analyst" if state.get("clauses") else "summarizer"

def build_analysis_graph():
    g = StateGraph(AgentState)
    g.add_node("extractor", extractor_agent)
    g.add_node("analyst", analyst_agent)
    g.add_node("summarizer", summarizer_agent)
    g.set_entry_point("extractor")
    g.add_conditional_edges("extractor", route_after_extraction, {"analyst": "analyst", "summarizer": "summarizer"})
    g.add_edge("analyst", "summarizer")
    g.add_edge("summarizer", END)
    return g.compile()

def build_qa_graph():
    g = StateGraph(AgentState)
    g.add_node("qa", qa_agent)
    g.set_entry_point("qa")
    g.add_edge("qa", END)
    return g.compile()

analysis_graph = build_analysis_graph()
qa_graph = build_qa_graph()

async def run_analysis(document_text: str, document_name: str, document_type: str = "Legal Contract") -> AgentState:
    initial: AgentState = {
        "document_text": document_text, "document_name": document_name,
        "document_type": document_type, "clauses": [], "analyzed_clauses": [],
        "executive_summary": None, "top_risks": None, "bottom_line": None,
        "overall_risk_score": None, "retrieved_chunks": [], "qa_question": None,
        "qa_answer": None, "errors": [], "current_agent": None,
    }
    print(f"\nPipeline starting: {document_name}")
    result = await analysis_graph.ainvoke(initial)
    print(f"Pipeline complete — risk: {result.get('overall_risk_score')}\n")
    return result

async def run_qa(state: AgentState, question: str, retrieved_chunks: list[str]) -> str:
    result = await qa_graph.ainvoke({**state, "qa_question": question, "retrieved_chunks": retrieved_chunks, "qa_answer": None})
    return result.get("qa_answer", "Unable to generate an answer.")


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="LegalLens API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

document_store: dict[str, dict] = {}
vector_store: dict[str, FAISS] = {}
result_store: dict[str, AgentState] = {}


def detect_document_type(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["non-disclosure", "confidential information", "nda"]): return "Non-Disclosure Agreement (NDA)"
    if any(w in t for w in ["employment", "employee", "employer", "salary"]):      return "Employment Contract"
    if any(w in t for w in ["lease", "tenant", "landlord", "rent", "premises"]):  return "Residential Lease Agreement"
    if any(w in t for w in ["terms of service", "terms and conditions"]):          return "Terms of Service"
    if any(w in t for w in ["privacy policy", "personal data", "gdpr"]):           return "Privacy Policy"
    if any(w in t for w in ["waiver", "release of liability"]):                    return "Liability Waiver"
    if any(w in t for w in ["contractor", "independent contractor"]):              return "Contractor Agreement"
    return "Legal Contract"

def extract_pdf(data: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    return "".join(p.extract_text() or "" for p in reader.pages).strip()

def extract_docx(data: bytes) -> str:
    doc = python_docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()

def build_faiss(text: str) -> FAISS:
    chunks = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50).split_text(text)
    embeddings = CohereEmbeddings(model="embed-english-v3.0", cohere_api_key=os.environ["COHERE_API_KEY"])
    return FAISS.from_texts(chunks, embeddings)


@app.get("/health")
def health():
    return {"status": "ok", "service": "LegalLens API"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    allowed = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if file.content_type not in allowed:
        raise HTTPException(400, "Only PDF and DOCX supported.")

    data = await file.read()
    text = extract_pdf(data) if file.content_type == "application/pdf" else extract_docx(data)

    if len(text) < 100:
        raise HTTPException(400, "Could not extract text. Is this a scanned image?")

    session_id = str(uuid.uuid4())
    doc_type = detect_document_type(text)
    document_store[session_id] = {"text": text, "name": file.filename, "type": doc_type}

    try:
        vector_store[session_id] = build_faiss(text)
    except Exception as e:
        print(f"Vector store failed: {e}")

    return {"session_id": session_id, "document_name": file.filename, "document_type": doc_type, "char_count": len(text)}


@app.get("/analyze/{session_id}")
async def analyze(session_id: str):
    if session_id not in document_store:
        raise HTTPException(404, "Session not found.")
    doc = document_store[session_id]

    async def stream() -> AsyncGenerator[str, None]:
        def sse(data): return f"data: {json.dumps(data)}\n\n"
        try:
            yield sse({"event": "progress", "agent": "extractor", "message": "Scanning for legal clauses..."})
            result = await run_analysis(doc["text"], doc["name"], doc["type"])
            yield sse({"event": "progress", "agent": "analyst", "message": f"Scoring {len(result.get('clauses', []))} clauses..."})
            yield sse({"event": "progress", "agent": "summarizer", "message": "Writing executive summary..."})
            result_store[session_id] = result
            yield sse({"event": "complete", "result": {
                "session_id": session_id,
                "document_name": result["document_name"],
                "document_type": result["document_type"],
                "overall_risk_score": result["overall_risk_score"],
                "executive_summary": result["executive_summary"],
                "top_risks": result["top_risks"],
                "bottom_line": result["bottom_line"],
                "analyzed_clauses": result["analyzed_clauses"],
                "errors": result["errors"],
            }})
        except Exception as e:
            yield sse({"event": "error", "message": str(e)})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/result/{session_id}")
def get_result(session_id: str):
    if session_id not in result_store:
        raise HTTPException(404, "No result yet. Run /analyze first.")
    r = result_store[session_id]
    return {**r, "session_id": session_id, "clause_count": len(r["analyzed_clauses"])}


class QARequest(BaseModel):
    question: str

@app.post("/qa/{session_id}")
async def ask(session_id: str, req: QARequest):
    if session_id not in result_store:
        raise HTTPException(404, "No analysis found. Run /analyze first.")
    if session_id not in vector_store:
        raise HTTPException(400, "Vector store unavailable.")
    docs = vector_store[session_id].similarity_search(req.question, k=4)
    answer = await run_qa(result_store[session_id], req.question, [d.page_content for d in docs])
    return {"question": req.question, "answer": answer}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
