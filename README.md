# QueueStorm Investigator
An intelligent AI-powered copilot service built for digital finance support agents. This service analyzes incoming customer support tickets, cross-references them against transaction logs to separate claims from truth, routes tickets to correct departments, and drafts highly localized, context-aware safe customer responses.

---

## 🚀 Tech Stack

* **Framework:** FastAPI (Python)
* **Validation:** Pydantic v2
* **LLM Provider:** Groq Client (using `grok-3-mini`)
* **Server Host:** Uvicorn

---

## 🧠 Architecture & AI Approach

The service adopts a **Hybrid Heuristic-LLM Architecture** to balance deterministic speed with linguistic intelligence:

1. **Strict Rule Engine Layer:** Initial parameters (`case_type`, `department`, `evidence_verdict`, `severity`, `human_review_required`) are processed deterministically via low-latency pattern-matching scripts. This ensures strict adherence to specific platform business rules, such as accurately routing duplicate payment anomalies.
2. **LLM Text Generation Layer:** The output of the rules engine is combined with the raw ticket fields and sent to Groq. The LLM handles tasks that require contextual understanding, such as writing professional multi-lingual summaries and responses.
3. **Strict JSON Output Enforcement:** By supplying `response_format={"type": "json_object"}` to the inference engine, the system prevents response parsing failure risks caused by formatting issues like raw Markdown backticks.

---

## 🛡️ Safety Logic & Guardrails

To prevent financial loss, operational issues, and safety penalties, the service enforces strict guardrails:

* **Anti-Commitment Phrasing:** The prompt forces the generation of non-committal phrasing (e.g., *"any eligible amount will be processed safely via official channels"*). It never promises direct refunds or account modifications.
* **Credential Masking:** The text synthesis system is strictly prohibited from echoing or requesting sensitive data tokens like a PIN, OTP, or password.
* **Mandatory Warning Interceptor:** Every customer response automatically appends a highly visible anti-fraud caution note: *"Please do not share your PIN or OTP with anyone."*
* **Robust Exception Fallback Logic:** If the external LLM provider encounters a network timeout, rate limit, or structural parsing error, an isolated local `except Exception` interceptor steps in. This immediately provides a safely constructed, pre-vetted hardcoded response block corresponding to the user's input language, preventing application crashes.

---

## 🖥️ Target Runtime Profile & Limits

* **Response Time:** `POST /analyze-ticket` responds under 30 seconds.
* **Health Checks:** `GET /health` initializes and registers immediately with a `{"status": "ok"}` response payload.
* **Infrastructure Sizing:** Configured for 2 vCPU and 4 GB RAM allocations without GPU requirements.

---

## 📖 Runbook: Local Setup & Reproduction

### Prerequisites
* Python 3.10+
* A valid Groq API Key

### 1. Clone the Project & Install Dependencies

* git clone https://github.com/12402111/queuestorm
* cd repofolder
* pip install -r requirements.txt

### 2. Run the app

* uvicorn main:app

### 3. Test Endpoints
* curl -X GET http://localhost:8000/health
* curl -X POST http://localhost:8000/analyze-ticket
