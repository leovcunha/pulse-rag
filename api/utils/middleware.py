import time
import structlog

logger = structlog.get_logger()

class StructlogASGIMiddleware:
    """
    Pure ASGI middleware for structured logging.
    Avoids Starlette's BaseHTTPMiddleware to prevent event loop future issues with streaming routes.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # The ASGI protocol supports 'http', 'websocket', and 'lifespan' connection scopes.
        # We only want to log standard HTTP web requests, so we pass through other types immediately.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        status_code = 500  # Default fallback status in case the route crashes completely
        is_streaming = False

        # In ASGI, outbound communications (sending headers, sending chunks) are made
        # by calling the async `send` callback function. To intercept response headers
        # and status codes, we wrap `send` in our own `send_wrapper` function.
        async def send_wrapper(message):
            nonlocal status_code, is_streaming
            
            # The 'http.response.start' event contains the HTTP headers and status code.
            if message["type"] == "http.response.start":
                status_code = message["status"]
                
                # Check headers to see if this response is a stream (e.g. text/event-stream).
                # message["headers"] is a list of [b"header-name", b"header-value"] tuples.
                headers = dict(message.get("headers", []))
                content_type = headers.get(b"content-type", b"").decode("utf-8")
                
                if "text/event-stream" in content_type:
                    is_streaming = True
                    
            # Pass the message along to the client/ASGI server unchanged
            await send(message)

        try:
            # Execute the downstream application handler, substituting our send wrapper
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # If an unhandled routing error occurs, mark it as 500 Internal Server Error
            status_code = 500
            raise e
        finally:
            # Log the request details ONLY for standard, non-streaming HTTP requests.
            # Streaming SSE routes (like /api/query) are logged directly inside their
            # event generator. This prevents printing a log before the stream has finished.
            if not is_streaming:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                logger.info(
                    "http_request",
                    path=scope["path"],
                    method=scope["method"],
                    http_status=status_code,
                    latency_ms=duration_ms
                )
