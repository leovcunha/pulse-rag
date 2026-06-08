import asyncio
import os
from api.services.llm import rewrite_query, stream_llm_response
from api.services.search import search_web_async
from api.services.rerank import rerank_results_async

QUERIES = [
    "onde comprar um cachorro golden retriever no brasil",
    "I'm getting a NullPointerException in Java when calling list.size()",
    "what are the latest advancements in quantum computing error correction?",
    "preciso de um encanador urgente em lisboa",
    "how to treat a mild sunburn at home",
    "best CRM for a small real estate agency",
    "como processar uma companhia aérea por atraso de voo",
    "music festivals happening in berlin this summer",
    "how to fix a leaky faucet in the kitchen",
    "melhores investimentos de renda fixa para 2026",
    "where can I learn python for data science for free",
    "authentic italian carbonara recipe without cream",
    "top things to do in kyoto during autumn",
    "best noise cancelling headphones under $100",
    "how to renew a US passport online",
    "who won the battle of waterloo and why",
    "comprar apartamento em moema são paulo",
    "best workout routine for building muscle mass in 3 months",
    "car makes a squeaking noise when braking",
    "when is the next season of stranger things coming out"
]

async def run_query_e2e(query):
    # 1. Rewrite
    rewritten = await rewrite_query(query, [])
    
    # 2. Search
    search_results, _ = await search_web_async(rewritten, max_results=5)
    
    # 3. Rerank
    reranked_results = []
    if search_results:
        reranked_results, _ = await rerank_results_async(rewritten, search_results)
    
    # 4. Generate Answer
    final_answer = ""
    if reranked_results:
        async for event in stream_llm_response(query, reranked_results, [], False):
            if event.get("type") == "token":
                final_answer += event.get("token", "")
    else:
        final_answer = "No search results found to generate answer."
        
    return rewritten, reranked_results, final_answer.strip()

async def main():
    md_content = "# End-to-End RAG Analysis\n\n"
    
    # Run only 10 to avoid excessive rate limits during testing, unless full 20 is needed.
    # Let's run all 20 but with a 2-second delay between them.
    for i, q in enumerate(QUERIES, 1):
        print(f"Processing E2E {i}/20: {q}")
        try:
            rewritten, sources, answer = await run_query_e2e(q)
            
            md_content += f"## {i}. Query: `{q}`\n"
            md_content += f"- **Rewritten:** `{rewritten}`\n"
            md_content += f"- **Sources Found:** {len(sources)}\n"
            md_content += f"### Final Answer:\n{answer}\n\n"
            md_content += "---\n"
            
        except Exception as e:
            md_content += f"## {i}. Query: `{q}`\n**ERROR:** {str(e)}\n\n---\n"
            print(f"Error on {i}: {e}")
            
        with open("e2e_results.md", "w", encoding="utf-8") as f:
            f.write(md_content)
            
        await asyncio.sleep(2.0)

if __name__ == "__main__":
    asyncio.run(main())
