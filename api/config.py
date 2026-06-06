import os
from dotenv import load_dotenv

# Load environment variables from local .env if available
load_dotenv()

# Clean up invalid SSL_CERT_FILE to prevent httpx/ssl from crashing on HTTPS requests
ssl_cert_file = os.environ.get("SSL_CERT_FILE")
if ssl_cert_file and not os.path.exists(ssl_cert_file):
    os.environ.pop("SSL_CERT_FILE", None)

class Settings:
    # API Keys
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    
    # API Endpoints
    TAVILY_API_URL: str = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")
    COHERE_RERANK_URL: str = os.getenv("COHERE_RERANK_URL", "https://api.cohere.com/v1/rerank")
    GROQ_URL: str = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
    OPENROUTER_URL: str = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
    
    # Model Configurations
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")
    
    # Rate Limiting Configuration
    SEARCH_RATE_LIMIT: str = os.getenv("SEARCH_RATE_LIMIT", "10/hour")

settings = Settings()
