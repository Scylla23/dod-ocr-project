import os

from dotenv import load_dotenv

# Load .env from the backend/ directory (one level above app/) so the
# server picks up ANTHROPIC_API_KEY, OPENAI_API_KEY, etc. without needing
# to prefix every uvicorn invocation. Falls back silently if no file.
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.routes import router  # noqa: E402

app = FastAPI(title="PDF Extract", root_path=os.getenv("ROOT_PATH", ""))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
