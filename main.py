import os
import json
import re
from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional, List, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

grok = OpenAI(
    api_key=os.environ.get("GROK_API_KEY"), 
    base_url="https://api.x.ai/v1"
)

# --- Schemas & Dept Map (Unchanged) ---
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
    transaction_history: Optional[List[TXN]] = []

    @field_validator("complaint")
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("complaint must not be empty")
        return v

DEPT_MAP = {
    "wrong_transfer": "dispute_resolution",
    "phishing_or_social_engineering": "fraud_risk",
    "duplicate_payment": "payments_ops",
    "payment_failed": "payments_ops",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "refund_request": "customer_support",
    "other": "customer_support",
}

# --- HELPER: Detect Bengali ---
def is_bangla_detected(text: str, lang_flag: str) -> bool:
    # Check if the flag is 'bn' OR if the text contains Bengali Unicode characters
    if lang_flag == "bn":
        return True
    return bool(re.search(r'[\u0980-\u09FF]', text))

# --- Logic Engines (Unchanged) ---
def classify_case(complaint: str) -> str:
    c = complaint.lower()
    if any(w in c for w in ["wrong number", "wrong person", "ভুল নম্বর", "sent to wrong"]): return "wrong_transfer"
    if any(w in c for w in ["phishing", "scam", "otp", "pin", "ওটিপি", "পিন"]): return "phishing_or_social_engineering"
    if any(w in c for w in ["duplicate", "charged twice", "deducted twice", "২ বার"]): return "duplicate_payment"
    if any(w in c for w in ["agent", "cash in", "এজেন্ট", "ক্যাশ ইন"]): return "agent_cash_in_issue"
    if "settlement" in c or "sales" in c: return "merchant_settlement_delay"
    if any(w in c for w in ["failed", "not received", "আসেনি"]): return "payment_failed"
    return "other"

def match_transaction(complaint: str, txns: list, case_type: str):
    if not txns: return None, "insufficient_data"
    if case_type == "duplicate_payment" and len(txns) >= 2: return txns[-1].transaction_id, "consistent"
    best = txns[0] # Default match
    return best.transaction_id, "consistent"

# --- FIXED: Dynamic Text Engine for Grok ---
def generate_dynamic_outputs(ticket: TicketRequest, case_type: str, txn_id: Optional[str], verdict: str, dept: str) -> dict:
    try:
        use_bn = is_bangla_detected(ticket.complaint, ticket.language)
        
        if use_bn:
            language_role = "The user is speaking BANGLA. You MUST provide the 'customer_reply' in BANGLA."
            safety_warning = "অনুগ্রহ করে আপনার পিন বা ওটিপি কারো সাথে শেয়ার করবেন না।"
        else:
            language_role = "The user is speaking ENGLISH. Provide the 'customer_reply' in ENGLISH."
            safety_warning = "Please do not share your PIN or OTP with anyone."

        prompt = f"""
        {language_role}
        
        Task: Analyze this fintech support ticket.
        - Complaint: "{ticket.complaint}"
        - Case Type: {case_type}
        - Relevant Txn: {txn_id}
        
        Requirements for JSON fields:
        1. 'agent_summary': Internal summary (Always English).
        2. 'recommended_next_action': Next step for agent (Always English).
        3. 'customer_reply': A polite response in the detected language. 
           - Use safe language: "any eligible amount will be returned".
           - DO NOT promise a refund.
           - MANDATORY ENDING: "{safety_warning}"

        Return JSON format:
        {{
          "agent_summary": "...",
          "recommended_next_action": "...",
          "customer_reply": "..."
        }}
        """

        resp = grok.chat.completions.create(
            model="grok-2-1212", 
            messages=[{"role": "system", "content": "You are a professional bank investigator."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1 # Low temperature ensures strict adherence to language
        )
        
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        # Fallback logic
        if is_bangla_detected(ticket.complaint, ticket.language):
            return {
                "agent_summary": f"Issue: {case_type}",
                "recommended_next_action": f"Escalate to {dept}",
                "customer_reply": "আমরা আপনার অভিযোগটি পেয়েছি। অনুগ্রহ করে আপনার পিন বা ওটিপি কারো সাথে শেয়ার করবেন না।"
            }
        return {
            "agent_summary": f"Issue: {case_type}",
            "recommended_next_action": f"Escalate to {dept}",
            "customer_reply": "We have received your concern. Please do not share your PIN or OTP with anyone."
        }

# --- Main Endpoint ---
@app.post("/analyze-ticket")
async def analyze_ticket(request: Request, payload: TicketRequest = Body(...)):
    try:
        await request.json()
    except:
        return JSONResponse(status_code=400, content={"error": "Malformed JSON structure"})

    try:
        ticket = payload 
        txns = ticket.transaction_history or []
        case_type = classify_case(ticket.complaint)
        txn_id, verdict = match_transaction(ticket.complaint, txns, case_type)
        dept = DEPT_MAP.get(case_type, "customer_support")

        text_outputs = generate_dynamic_outputs(ticket, case_type, txn_id, verdict, dept)

        return {
            "ticket_id": ticket.ticket_id,
            "relevant_transaction_id": txn_id,
            "evidence_verdict": verdict,
            "case_type": case_type,
            "severity": "high" if case_type in ["wrong_transfer", "phishing_or_social_engineering"] else "medium",
            "department": dept,
            "agent_summary": text_outputs.get("agent_summary"),
            "recommended_next_action": text_outputs.get("recommended_next_action"),
            "customer_reply": text_outputs.get("customer_reply"),
            "human_review_required": True if case_type in ["wrong_transfer", "phishing_or_social_engineering"] else False,
            "confidence": 0.90,
            "reason_codes": [case_type, verdict]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
def health(): return {"status": "ok"}