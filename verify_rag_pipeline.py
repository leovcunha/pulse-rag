import asyncio
import json
import httpx

GATEWAY_URL = "http://127.0.0.1:8000"

async def test_health():
    print("Testing backend health endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{GATEWAY_URL}/health")
            print(f"Health Response: Status {resp.status_code}, Body: {resp.json()}")
            return resp.status_code == 200
        except Exception as e:
            print(f"Failed to connect to health endpoint: {e}")
            return False

async def test_rag_streaming():
    print("\nTesting RAG Streaming pipeline...")
    query_payload = {
        "query": "What is the latest status of SpaceX Starship launch?"
    }
    
    events_received = []
    has_error = False

    try:
        # 10 second timeout for the initial connection and streaming
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{GATEWAY_URL}/api/query", json=query_payload) as response:
                print(f"SSE Connection Status: {response.status_code}")
                if response.status_code != 200:
                    print("Error: RAG query returned non-200 status code.")
                    return False

                current_event = None
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith("event: "):
                        current_event = line[7:]
                    elif line.startswith("data: "):
                        data_payload = line[6:]
                        try:
                            parsed_data = json.loads(data_payload)
                            events_received.append((current_event, parsed_data))
                            
                            # Print some feedback
                            if current_event == "status":
                                print(f"Stage Status -> {parsed_data.get('status')}")
                            elif current_event == "provider":
                                print(f"LLM Provider -> {parsed_data.get('provider')}")
                            elif current_event == "ttft":
                                print(f"LLM TTFT -> {parsed_data.get('ttft_ms'):.1f}ms")
                            elif current_event == "token":
                                # Just print dots for tokens to avoid messy stdout
                                print(".", end="", flush=True)
                            elif current_event == "metrics":
                                print("\nPipeline Complete. Latency Metrics Received:")
                                for k, v in parsed_data.items():
                                    print(f"  - {k}: {v:.1f}ms" if isinstance(v, float) else f"  - {k}: {v}")
                            elif current_event == "error":
                                print(f"\nPipeline Error -> {parsed_data.get('message')}")
                                has_error = True
                            elif current_event == "fallback_alert":
                                print(f"\nLLM Alert -> {parsed_data.get('message')}")
                        except json.JSONDecodeError:
                            print(f"\nFailed to parse JSON data line: {line}")
                            
    except Exception as e:
        print(f"\nFailed to run streaming test: {e}")
        return False

    # Check if we got the basic sequence of statuses
    statuses = [data.get("status") for event, data in events_received if event == "status"]
    print(f"\nSequence of status events received: {statuses}")
    
    # We expect to see searching, reranking, generating, and completed if no error
    expected = ["searching", "reranking", "generating", "completed"]
    if has_error:
        print("Pipeline run encountered a logical error. Check if API keys are configured.")
        return False
        
    for stage in ["searching", "reranking", "generating"]:
        if stage not in statuses:
            print(f"Warning: Expected stage '{stage}' was not found in status list.")
            return False
            
    print("Integration test check: SUCCESS. RAG state transitions work as expected!")
    return True

async def main():
    health_ok = await test_health()
    if not health_ok:
        print("Please start the FastAPI server with 'uvicorn api.main:app --reload' before running this test.")
        return
        
    await test_rag_streaming()

if __name__ == "__main__":
    asyncio.run(main())
