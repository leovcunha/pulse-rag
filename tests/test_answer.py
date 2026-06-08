import asyncio
from api.services.llm import stream_llm_response
from api.schemas.query import SearchResult

async def main():
    query = "AI applications in power grids"
    sources = [
        SearchResult(title="AI in Power Grids", url="http://example.com/1", content="Artificial intelligence is transforming energy grids through optimization, predictive maintenance, and efficiency improvements. Machine learning models predict grid failures.", score=0.9),
        SearchResult(title="Smart Grid Technologies", url="http://example.com/2", content="Smart grids use artificial neural networks and deep learning for real-time load forecasting, power flow control, and autonomous system balancing.", score=0.8),
        SearchResult(title="Explainable AI for Energy", url="http://example.com/3", content="Explainable AI (XAI) provides transparent energy management, fault detection, and design optimization for power grids.", score=0.7)
    ]
    
    print("Streaming LLM Response:")
    async for chunk in stream_llm_response(query, sources, history=None):
        if chunk.get("type") == "token":
            print(chunk.get("token"), end="", flush=True)
    print("\n\nFinished streaming.")

if __name__ == "__main__":
    asyncio.run(main())
