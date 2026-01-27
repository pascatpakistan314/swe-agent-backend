"""Simple API server for SWE Agent with proper authentication and async-safe agent calls"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Set, List
from starlette.concurrency import run_in_threadpool

import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# ===================== ENV & LOGGING =====================
# Load .env from the script directory FIRST, then from CWD as fallback.
_own_env = Path(__file__).with_name(".env")
if _own_env.exists():
    load_dotenv(dotenv_path=_own_env, override=False)
load_dotenv(override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("swe_api")

def _clean_token(s: str) -> str:
    # Trim whitespace and surrounding quotes
    return s.strip().strip('"').strip("'")

def _split_tokens(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = [raw]
    for sep in (",", ";", " ", "\n", "\t"):
        parts = [p for chunk in parts for p in chunk.split(sep)]
    return [_clean_token(p) for p in parts if _clean_token(p)]

def get_allowed_tokens() -> Set[str]:
    # Supports either a single token or multiple
    single = _split_tokens(os.getenv("SWE_API_TOKEN", ""))
    multi = _split_tokens(os.getenv("SWE_API_TOKENS", ""))
    return set(single + multi)

ALLOW_QUERY_TOKEN = os.getenv("ALLOW_QUERY_TOKEN", "false").lower() == "true"
AUTH_DEBUG = os.getenv("SWE_AUTH_DEBUG", "false").lower() == "true"
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "./workspace_repo")

# Anthropic key for the underlying agent
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    logger.error("ANTHROPIC_API_KEY not found in environment variables! Add it to your .env.")
else:
    logger.info("Anthropic API key loaded")
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY  # ensure downstream libs see it

# Import the ORCHESTRATED agent AFTER env is ready
try:
    # Try to use the orchestrated agent with all features
    from agent.orchestrated_agent import orchestrated_swe_agent_compatible as swe_agent
    logger.info("Using ORCHESTRATED agent with multi-agent support, GitHub integration, and multi-language features")
except ImportError as e:
    # Fallback to integrated agent if orchestrated fails
    logger.warning(f"Could not load orchestrated agent: {e}")
    try:
        from agent.integrated_graph import swe_agent
        logger.info("Using INTEGRATED agent (architect + developer)")
    except ImportError as e2:
        # Final fallback to basic agent
        logger.warning(f"Could not load integrated agent: {e2}")
        logger.info("Falling back to basic graph agent")
        from agent.graph import swe_agent

# ===================== FASTAPI APP =====================
app = FastAPI(
    title="SWE Agent API",
    description="AI-powered Software Engineering Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== AUTH =====================
bearer_scheme = HTTPBearer(auto_error=False)
x_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

@app.on_event("startup")
async def _startup_report():
    toks = list(get_allowed_tokens())
    if toks:
        masks = [f"...{t[-4:]}" if len(t) >= 4 else "..." for t in toks]
        logger.info(f"Auth tokens configured: {len(toks)} ({', '.join(masks)})")
    else:
        logger.warning("No SWE_API_TOKEN/SWE_API_TOKENS set. Auth will reject all requests.")

@app.on_event("startup")
async def _ensure_workspace_dir():
    os.makedirs(WORKSPACE_DIR, exist_ok=True)

async def require_auth(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Depends(x_api_key_scheme),
) -> None:
    allowed = get_allowed_tokens()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfigured: set SWE_API_TOKEN or SWE_API_TOKENS in the environment.",
        )

    provided: Optional[str] = None
    # Prefer Authorization: Bearer <token>
    if bearer and (bearer.scheme or "").lower() == "bearer":
        provided = bearer.credentials
    # Or X-API-Key: <token>
    if not provided and x_api_key:
        provided = x_api_key
    # Optional: allow ?token= for quick local testing (set ALLOW_QUERY_TOKEN=true in .env)
    if not provided and ALLOW_QUERY_TOKEN:
        provided = request.query_params.get("token")

    if not provided or _clean_token(provided) not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
        )

# ===================== MODELS =====================
class AgentRequest(BaseModel):
    task: str = Field(..., description="Task description")
    context: Optional[str] = Field(None, description="Additional context")

class AgentResponse(BaseModel):
    success: bool
    implementation_plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ===================== AGENT CALL (ASYNC-SAFE) =====================
async def run_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    ainvoke = getattr(swe_agent, "ainvoke", None)
    if callable(ainvoke):
        return await ainvoke(payload)
    return await run_in_threadpool(swe_agent.invoke, payload)

# ===================== ROUTES =====================
@app.get("/")
async def root():
    return {
        "name": "SWE Agent API",
        "version": "1.0.0",
        "endpoints": {"POST /execute": "Execute agent task", "GET /health": "Health check"},
        "anthropic_key_loaded": bool(ANTHROPIC_API_KEY),
        "auth_required": True,
        "auth_configured": bool(get_allowed_tokens()),
        "auth_header": "Authorization: Bearer <SWE_API_TOKEN>  or  X-API-Key: <SWE_API_TOKEN>",
        "workspace_dir": WORKSPACE_DIR,
    }

@app.get("/debug/auth")
async def debug_auth():
    if not AUTH_DEBUG:
        # Hide this unless explicitly enabled
        raise HTTPException(status_code=404, detail="Not found.")
    toks = list(get_allowed_tokens())
    masks = [f"...{t[-4:]}" if len(t) >= 4 else "..." for t in toks]
    return {
        "configured_tokens": masks,
        "allow_query_token": ALLOW_QUERY_TOKEN,
        "note": "Values are masked. Set SWE_AUTH_DEBUG=false to disable this endpoint.",
    }

@app.post("/execute", response_model=AgentResponse, dependencies=[Depends(require_auth)])
async def execute_agent(request: AgentRequest):
    if not os.getenv("ANTHROPIC_API_KEY"):
        return AgentResponse(success=False, error="ANTHROPIC_API_KEY not configured in .env")

    try:
        logger.info(f"Executing task: {request.task[:100]}...")

        initial_state = {
            "task_description": request.task,                 # <-- REQUIRED by Architect graph
            "implementation_research_scratchpad": [],
        }

        # (Optional) keep messages if other parts of your graph use them:
        if request.context:
            initial_state["messages"] = [
                {"role": "user", "content": request.task},
                {"role": "user", "content": f"Context: {request.context}"},
            ]

        result = await run_agent(initial_state)

        # Extract and convert implementation_plan to dict
        impl = result.get("implementation_plan") if isinstance(result, dict) else None
        if impl:
            # If it's a Pydantic model, convert to dict
            if hasattr(impl, 'model_dump'):
                impl = impl.model_dump()
            elif hasattr(impl, 'dict'):
                impl = impl.dict()
        
        logger.info("Task completed successfully")
        return AgentResponse(success=True, implementation_plan=impl)

    except Exception as e:
        logger.exception("Error executing agent")
        return AgentResponse(success=False, error=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "anthropic_key_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "langsmith_configured": bool(os.getenv("LANGSMITH_API_KEY")),
        "auth_configured": bool(get_allowed_tokens()),
        "workspace_dir_exists": os.path.isdir(WORKSPACE_DIR),
    }

# ===================== MAIN =====================
if __name__ == "__main__":
    import uvicorn
    workspace_dir = os.getenv("WORKSPACE_DIR", "./workspace_repo")
    os.makedirs(workspace_dir, exist_ok=True)

    if not ANTHROPIC_API_KEY:
        print("\n" + "=" * 60)
        print("ERROR: ANTHROPIC_API_KEY not found!")
        print("=" * 60)
        print("Add to C:\\ZIP_SWE\\swe-agent\\.env and restart:")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        print("  SWE_API_TOKEN=<your-token>  (or SWE_API_TOKENS=a,b,c)")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("SWE Agent API Server")
        print("=" * 60)
        print("[OK] Anthropic API key loaded")
        print(f"[OK] Workspace directory: {workspace_dir}")
        print("[OK] Starting server on http://0.0.0.0:8000")
        print("=" * 60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)