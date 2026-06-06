import os
import logging

# Clean up invalid SSL_CERT_FILE to prevent httpx/ssl from crashing on HTTPS requests
ssl_cert_file = os.environ.get("SSL_CERT_FILE")
if ssl_cert_file and not os.path.exists(ssl_cert_file):
    del os.environ["SSL_CERT_FILE"]

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.utils.rate_limiter import limiter
from api.routes.query import router as query_router

from api.utils.logging import setup_logging
from api.utils.middleware import StructlogASGIMiddleware

# Initialize structlog configuration
setup_logging()
# Load environment variables
load_dotenv()

app = FastAPI(
    title="Low-Latency RAG Gateway",
    description="High-performance backend routing web queries, reranking results, and streaming cited answers.",
    version="1.0.0"
)

# Register rate limiter with FastAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

# Add custom structured logging middleware
app.add_middleware(StructlogASGIMiddleware)

# Configure CORS
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

prod_origin = os.environ.get("ALLOWED_ORIGIN")
if prod_origin:
    allowed_origins.append(prod_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Gateway is responsive and running."}

if __name__ == "__main__":
    import uvicorn
    import pathlib
    
    # Restrict reload scanning to the 'api' directory to avoid searching client/node_modules/
    api_dir = str(pathlib.Path(__file__).parent)
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=[api_dir])
