import os
import json
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from typing import Optional, List, Any
from openai import OpenAI

app = FastAPI()

# ── Grok client (xAI uses OpenAI-compatible API) ──────────────────────────────
grok = OpenAI(
    api_key=os.environ.get("GROK_API_KEY", "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"),
    base_url="https://api.x.ai/v1"
)

# ── Request model ─────────────────────────────────────────────────────────────
class TXN(BaseModel):
    transaction_id: str
    timestamp: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    counterparty: Optional[str] = None
    status: Optional[str] = None

class TicketRequest(BaseModel):
    ticket_id: str
    complaint: str
    language: Optional[str] = "en"
    channel: Optional[str] = None
    user_type: Optional[str] = "customer"
    campaign_context: Optional[str] = None
    transaction_history: Optional[List[TXN]] = []
    metadata: Optional[Any] = None

    @validator("complaint")
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("complaint must not be empty")
        return v

# ── RULE ENGINE ───────────────────────────────────────────────────────────────

def classify_case(complaint: str, txns: list) -> str:
    c = complaint.lower()
    if any(w in c for w in ["wrong number", "wrong person", "wrong recipient", "ভুল নম্বর", "sent to wrong"]):
        return "wrong_transfer"
    if any(w in c for w in ["phishing", "scam", "otp", "pin", "password", "suspicious call", "fake", "fraud call"]):
        return "phishing_or_social_engineering"
    if any(w in c for w in ["duplicate", "charged twice", "double", "same payment"]):
        return "duplicate_payment"
    if any(w in c for w in ["merchant", "shop", "store", "settlement", "payment not received"]):
        if any(w in c for w in ["settlement", "not received", "delay"]):
            return "merchant_settlement_delay"
    if any(w in c for w in ["agent", "cash in", "deposit", "not reflected", "balance not updated"]):
        return "agent_cash_in_issue"
    if any(w in c for w in ["failed", "deducted", "balance cut", "not received", "transaction failed", "unsuccessful"]):
        return "payment_failed"
    if any(w in c for w in ["refund", "money back", "return", "reimburs"]):
        return "refund_request"
    return "other"

DEPT_MAP = {
    "wrong_transfer": "dispute_resolution",
    "phishing_or_social_engineering": "fraud_risk",
    "duplicate_payment": "payments_ops",
    "payment_failed": "payments_ops",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "refund_request": "dispute_resolution",
    "other": "customer_support",
}

def get_severity(case_type: str, amount: Optional[float], evidence: str) -> str:
    if case_type == "phishing_or_social_engineering":
        return "critical"
    if amount and amount >= 10000:
        return "high"
    if case_type in ("wrong_transfer", "duplicate_payment") or evidence == "inconsistent":
        return "high"
    if amount and amount >= 2000:
        return "medium"
    if case_type in ("payment_failed", "refund_request"):
        return "medium"
    return "low"

def match_transaction(complaint: str, txns: list):
    """Return (transaction_id or None, evidence_verdict)"""
    if not txns:
        return None, "insufficient_data"

    c = complaint.lower()

    # Try to find amount mentioned in complaint
    amounts = re.findall(r"(\d[\d,]*)\s*(?:taka|bdt|tk)?", c)
    mentioned_amounts = set()
    for a in amounts:
        try:
            mentioned_amounts.add(float(a.replace(",", "")))
        except:
            pass

    best = None
    for t in txns:
        # Keyword match by type
        if t.type == "transfer" and any(w in c for w in ["sent", "transfer", "send", "wrong number", "wrong person"]):
            best = t; break
        if t.type == "payment" and any(w in c for w in ["payment", "paid", "merchant", "shop"]):
            best = t; break
        if t.type in ("cash_in", "cash_out") and any(w in c for w in ["cash", "deposit", "agent"]):
            best = t; break
        if t.type == "refund" and "refund" in c:
            best = t; break

    # Fallback: pick by amount match
    if not best and mentioned_amounts:
        for t in txns:
            if t.amount and t.amount in mentioned_amounts:
                best = t; break

    # Fallback: first transaction
    if not best:
        best = txns[0]

    if best is None:
        return None, "insufficient_data"

    # Determine evidence verdict
    txn_id = best.transaction_id
    if best.status == "completed":
        # Customer complains about wrong transfer / payment — the tx exists and completed → consistent
        if any(w in c for w in ["wrong", "failed", "not received", "not credited"]):
            if "failed" in c or "not received" in c:
                # They say failed but tx is completed → inconsistent
                verdict = "inconsistent"
            else:
                verdict = "consistent"
        else:
            verdict = "consistent"
    elif best.status == "failed":
        if any(w in c for w in ["failed", "deducted", "not received", "unsuccessful"]):
            verdict = "consistent"
        else:
            verdict = "inconsistent"
    elif best.status == "pending":
        verdict = "insufficient_data"
    else:
        verdict = "consistent"

    return txn_id, verdict

def needs_human(case_type: str, severity: str, verdict: str) -> bool:
    if case_type in ("wrong_transfer", "phishing_or_social_engineering", "duplicate_payment"):
        return True
    if severity in ("high", "critical"):
        return True
    if verdict in ("inconsistent", "insufficient_data"):
        return True
    return False

# ── Safe reply templates (no LLM needed, fully safe) ─────────────────────────
SAFE_REPLIES = {
    "wrong_transfer": "Thank you for contacting us. We have received your report regarding the transfer. Our team will investigate the details and any eligible amount will be returned through official channels. Please do not share your account credentials with anyone.",
    "phishing_or_social_engineering": "We take security concerns very seriously. Please do not share your PIN, OTP, or password with anyone — including callers claiming to be from our support team. Our team has flagged this for immediate review. Stay safe and contact us only through official channels.",
    "payment_failed": "Thank you for reaching out. We have noted your concern about the transaction. Our payments team will review the details and update you through the official app or registered contact.",
    "duplicate_payment": "We have received your concern about a possible duplicate charge. Our team will review the transaction records and any eligible amount will be returned through official channels.",
    "merchant_settlement_delay": "We understand your concern about the pending settlement. Our merchant operations team will review the case and reach out to you within the standard resolution window.",
    "agent_cash_in_issue": "We have noted your cash-in concern. Our agent operations team will verify the transaction with the relevant agent and update your account accordingly if a discrepancy is confirmed.",
    "refund_request": "We have received your refund request. Our team will review the case and any eligible amount will be returned through official channels. We will keep you updated.",
    "other": "Thank you for contacting us. We have received your complaint and our support team will review it shortly. Please use only official channels for follow-up.",
}

# ── Grok: generate agent_summary + recommended_next_action only ───────────────
def grok_text(complaint: str, case_type: str, txn_id: Optional[str], verdict: str, amount: Optional[float]) -> dict:
    try:
        prompt = f"""You are a fintech support assistant. Write two short pieces of text in plain English.

Case:
- Complaint: {complaint[:300]}
- Case type: {case_type}
- Relevant transaction: {txn_id or 'none found'}
- Evidence verdict: {verdict}
- Amount: {amount} BDT

Return ONLY this JSON (no markdown):
{{
  "agent_summary": "1-2 sentence internal summary for the support agent",
  "recommended_next_action": "one actionable step for the agent to take next"
}}"""

        resp = grok.chat.completions.create(
            model="grok-3-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        # Fallback if Grok fails
        return {
            "agent_summary": f"Customer complaint classified as {case_type}. Relevant transaction: {txn_id or 'not identified'}. Evidence verdict: {verdict}.",
            "recommended_next_action": f"Review the case details and escalate to {DEPT_MAP.get(case_type, 'customer_support')} for resolution."
        }

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze-ticket")
async def analyze_ticket(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    try:
        ticket = TicketRequest(**body)
    except ValueError as e:
        code = 422 if "empty" in str(e).lower() else 400
        return JSONResponse(status_code=code, content={"error": str(e)})

    try:
        txns = ticket.transaction_history or []
        complaint = ticket.complaint

        # Rule-based core
        case_type = classify_case(complaint, txns)
        txn_id, verdict = match_transaction(complaint, txns)
        dept = DEPT_MAP.get(case_type, "customer_support")

        # Get amount from matched txn for severity
        matched_amount = None
        for t in txns:
            if t.transaction_id == txn_id:
                matched_amount = t.amount
                break

        severity = get_severity(case_type, matched_amount, verdict)
        human_review = needs_human(case_type, severity, verdict)
        customer_reply = SAFE_REPLIES.get(case_type, SAFE_REPLIES["other"])

        # Grok for text fields only
        grok_fields = grok_text(complaint, case_type, txn_id, verdict, matched_amount)

        result = {
            "ticket_id": ticket.ticket_id,
            "relevant_transaction_id": txn_id,
            "evidence_verdict": verdict,
            "case_type": case_type,
            "severity": severity,
            "department": dept,
            "agent_summary": grok_fields["agent_summary"],
            "recommended_next_action": grok_fields["recommended_next_action"],
            "customer_reply": customer_reply,
            "human_review_required": human_review,
            "confidence": 0.85,
            "reason_codes": [case_type, verdict, f"dept_{dept}"]
        }

        return JSONResponse(status_code=200, content=result)

    except Exception:
        return JSONResponse(status_code=500, content={"error": "Internal analysis error"})
