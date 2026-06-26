QueueStorm Investigator — AI/API SupportOps Copilot
An intelligent AI-powered copilot service built for digital finance support agents. This service analyzes incoming customer support tickets, cross-references them against transaction logs to separate claims from truth, routes tickets to correct departments, and drafts highly localized, context-aware safe customer responses.

🚀 Tech Stack
Framework: FastAPI (Python)

Validation: Pydantic v2

LLM Provider: Groq Client (using grok-3-mini)

Server Host: Uvicorn

🧠 Architecture & AI Approach
The service adopts a Hybrid Heuristic-LLM Architecture to balance deterministic speed with linguistic intelligence:

Strict Rule Engine Layer: Initial parameters (case_type, department, evidence_verdict, severity, human_review_required) are processed deterministically via low-latency pattern-matching scripts. This ensures strict adherence to specific platform business rules, such as accurately routing duplicate payment anomalies.

LLM Text Generation Layer: The output of the rules engine is combined with the raw ticket fields and sent to Groq. The LLM handles tasks that require contextual understanding, such as writing professional multi-lingual summaries and responses.

Strict JSON Output Enforcement: By supplying response_format={"type": "json_object"} to the inference engine, the system prevents response parsing failure risks caused by formatting issues like raw Markdown backticks.

🛡️ Safety Logic & Guardrails
To prevent financial loss, operational issues, and safety penalties, the service enforces strict guardrails:

Anti-Commitment Phrasing: The prompt forces the generation of non-committal phrasing (e.g., "any eligible amount will be processed safely via official channels"). It never promises direct refunds or account modifications.

Credential Masking: The text synthesis system is strictly prohibited from echoing or requesting sensitive data tokens like a PIN, OTP, or password.

Mandatory Warning Interceptor: Every customer response automatically appends a highly visible anti-fraud caution note: "Please do not share your PIN or OTP with anyone."

Robust Exception Fallback Logic: If the external LLM provider encounters a network timeout, rate limit, or structural parsing error, an isolated local except Exception interceptor steps in. This immediately provides a safely constructed, pre-vetted hardcoded response block corresponding to the user's input language, preventing application crashes.

🖥️ Target Runtime Profile & Limits
Response Time: POST /analyze-ticket responds under 30 seconds.

Health Checks: GET /health initializes and registers immediately with a {"status": "ok"} response payload.

Infrastructure Sizing: Configured for 2 vCPU and 4 GB RAM allocations without GPU requirements.

📖 Runbook: Local Setup & Reproduction
Prerequisites
Python 3.10+

A valid Groq API Key

1. Clone the Project & Install Dependencies
Bash
git clone <your-repo-url>
cd <your-repo-folder>
pip install -r requirements.txt
2. Configure Environment Variables
Create a .env file or export your API credentials directly to your shell profile:

Bash
export GROQ_API_KEY="your-actual-groq-api-key-here"
3. Start the Server Instance
Bash
python main.py
The server will boot up and start listening on: http://127.0.0.1:8000.

4. Interactive OpenAPI Testing
Open your browser and navigate to http://127.0.0.1:8000/docs to open the fully interactive Swagger UI interface. Here, you can live-test sample schema inputs against the system.

🔮 Model Selection & Cost Reasoning
Models Used
grok-3-mini (Accessed via the Groq API Cloud Client Interface)

Reasoning
Ultra-Low Latency: The mini model series optimized by Groq's LPU inference system provides token delivery speeds that easily clear the 30-second request timeout limit.

Multilingual Competency: It reliably structures accurate cross-lingual transformations (English, Bangla, and Banglish text expressions) without losing track of systemic safety context boundaries.

High Cost-Efficiency: Using a smaller model ensures minimal cost overhead while still providing excellent compliance with the structured JSON output format.
