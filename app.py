import os
import sys
from typing import List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure local modules can be loaded
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import agent

app = FastAPI(
    title="Customer Support Assistant API",
    description="Guidance-focused customer support assistant API based on AmazonHelp TWCS prototype.",
    version="1.0.0",
)

# Enable CORS so frontend can communicate even if served from a different port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="The customer query or message",
        example="How can I check my order status?"
    )


class RetrievedCase(BaseModel):
    customer_text: Optional[str] = ""
    amazon_text: Optional[str] = ""
    similarity: Optional[float] = 0.0


class ChatResponse(BaseModel):
    intent: str
    should_escalate: bool
    escalation_reason: Optional[str] = ""
    reply: str
    retrieved_cases: List[RetrievedCase] = []


@app.get("/health", tags=["System"])
def health_check():
    """
    Check the backend service health and LLM provider configuration.
    """
    keys_configured, key_error = agent.validate_api_keys(exit_on_error=False)
    provider = agent.get_current_provider()
    return {
        "status": "ok" if keys_configured else "degraded",
        "provider": provider,
        "configured": keys_configured,
        "message": "Ready" if keys_configured else key_error,
    }


@app.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    tags=["Chat"]
)
def chat_endpoint(payload: ChatRequest):
    """
    Process an incoming customer query through the existing agent pipeline:
      1. Intent classification
      2. TF-IDF retrieval of historical cases
      3. Deterministic escalation logic
      4. Grounded response drafting
      5. Post-generation safety validation
      6. Safe fallback (if needed)
    """
    clean_message = payload.message.strip() if payload.message else ""
    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty or contain only whitespace."
        )

    try:
        result = agent.process_message(clean_message)

        # Normalize retrieved cases format
        cases = []
        for c in result.get("retrieved_cases", []):
            cases.append(
                RetrievedCase(
                    customer_text=c.get("customer_text", ""),
                    amazon_text=c.get("amazon_text", ""),
                    similarity=round(float(c.get("similarity", 0.0)), 3),
                )
            )

        return ChatResponse(
            intent=result.get("intent", "other"),
            should_escalate=bool(result.get("should_escalate", False)),
            escalation_reason=result.get("escalation_reason") or "",
            reply=result.get("reply", ""),
            retrieved_cases=cases,
        )

    except RuntimeError as re_err:
        # Configuration or LLM provider errors
        err_msg = str(re_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chatbot service unavailable: {err_msg}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


# Mount static assets if the static directory exists
static_path = os.path.join(current_dir, "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(os.path.join(static_path, "index.html"))

    @app.get("/index.html", include_in_schema=False)
    def serve_index_html():
        return FileResponse(os.path.join(static_path, "index.html"))


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Customer Support Chatbot API on http://{host}:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=True)

