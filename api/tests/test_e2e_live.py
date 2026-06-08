import pytest
import asyncio
import httpx
from api.main import app

@pytest.mark.asyncio
async def test_live_e2e_pipeline():
    """
    Live End-to-End test hitting actual APIs (Groq, Tavily, Cohere).
    Tests the RAG pipeline with a few diverse queries to verify end-to-end plausibility.
    We include sleeps to respect rate limits.
    """
    test_queries = [
        "What are the best open source reasoning models?",
        "onde comprar um gato ragdoll na alemanha",
        "ho bisogno di un idraulico urgente a lisbona",
        "flagelar motor in cells"
    ]
    
    transport = httpx.ASGITransport(app=app)
    
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as ac:
        for query in test_queries:
            print(f"\n--- Testing E2E: {query} ---")
            events_received = set()
            full_response = ""
            
            async with ac.stream("POST", "/api/query", json={"query": query}) as response:
                assert response.status_code == 200
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                        
                    if line.startswith("event:"):
                        event_type = line.replace("event:", "").strip()
                        events_received.add(event_type)
                    
                    elif line.startswith("data:"):
                        data_val = line.replace("data:", "").strip()
                        if "status" in events_received and '"generating"' in data_val:
                            pass # Status update
                        elif "token" in events_received:
                            full_response += data_val
                
                print("Events received:", events_received)
                if "error" in events_received:
                    print("Error occurred in SSE stream!")
                
                # Verify the pipeline progressed through all crucial stages
                assert "status" in events_received
                assert "sources" in events_received
                assert "provider" in events_received
                assert "token" in events_received
            assert "metrics" in events_received
            
            assert len(full_response) > 20, "LLM failed to generate a substantial response"
            print(f"Success! Response length: {len(full_response)} chars")
            
            # Sleep to prevent hitting free-tier API rate limits during testing
            await asyncio.sleep(15)
