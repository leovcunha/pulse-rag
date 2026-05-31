import os
from dotenv import load_dotenv

# Load environment variables from local .env if available
load_dotenv()

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
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

settings = Settings()
