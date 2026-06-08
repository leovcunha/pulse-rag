import asyncio
import os
from api.services.llm import rewrite_query, stream_llm_response
from api.services.search import search_web_async
from api.services.rerank import rerank_results_async

QUERIES = [
    # 1. French: Animal Purchase in Germany
    "où acheter un chat ragdoll en allemagne",
    # 2. Italian: Local Service in Portugal
    "ho bisogno di un idraulico urgente a lisbona",
    # 3. Spanish: Academic / Documentation
    "cuales son los ultimos avances en correccion de errores de computacion cuantica",
    # 4. French: Medical / DIY
    "comment traiter un coup de soleil léger à la maison",
    # 5. Spanish: Official documentation
    "como renovar el pasaporte de USA por internet"
]

async def run_query_e2e(query):
    # 1. Rewrite
    rewritten = await rewrite_query(query, [])
    
    # 2. Search
    search_results, _ = await search_web_async(rewritten, max_results=3)
    
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
    md_content = "# Multilingual End-to-End RAG Analysis\n\n"
    
    for i, q in enumerate(QUERIES, 1):
        print(f"Processing E2E {i}/{len(QUERIES)}: {q}")
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
            
        with open("multilingual_results.md", "w", encoding="utf-8") as f:
            f.write(md_content)
            
        # 5 second sleep to avoid Groq rate limits
        await asyncio.sleep(5.0)

if __name__ == "__main__":
    asyncio.run(main())
