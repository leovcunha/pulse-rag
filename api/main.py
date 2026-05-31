import os
import logging

# Clean up invalid SSL_CERT_FILE to prevent httpx/ssl from crashing on HTTPS requests
ssl_cert_file = os.environ.get("SSL_CERT_FILE")
if ssl_cert_file and not os.path.exists(ssl_cert_file):
    del os.environ["SSL_CERT_FILE"]

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes.query import router as query_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Sub-2-Second RAG Gateway",
    description="High-performance backend routing web queries, reranking results, and streaming cited answers.",
    version="1.0.0"
)

# Configure CORS for React/Vite development server (port 5173 and 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
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
