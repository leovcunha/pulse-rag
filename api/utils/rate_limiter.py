import logging
from fastapi import Request
from slowapi import Limiter

logger = logging.getLogger(__name__)

def get_real_ip(request: Request) -> str:
    """
    Extracts the client's real IP address.
    Checks the X-Forwarded-For header first (to handle cloud load balancers/proxies)
    and falls back to request.client.host for local testing.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can contain a comma-separated list of proxy IPs.
        # The first IP is typically the original client.
        client_ip = x_forwarded_for.split(",")[0].strip()
        return client_ip
    
    if request.client:
        return request.client.host
        
    return "127.0.0.1"

# Initialize Limiter with in-memory storage (default) using the custom IP resolver
limiter = Limiter(key_func=get_real_ip)
