import asyncio
import os
from api.services.llm import rewrite_query
from api.services.search import search_web_async

QUERIES = [
    # 1. Animal purchase (Localization + Breeder)
    "onde comprar um cachorro golden retriever no brasil",
    # 2. Software bug (Troubleshooting)
    "I'm getting a NullPointerException in Java when calling list.size()",
    # 3. Academic research
    "what are the latest advancements in quantum computing error correction?",
    # 4. Local Service (Localization + Contractor)
    "preciso de um encanador urgente em lisboa",
    # 5. Medical condition
    "how to treat a mild sunburn at home",
    # 6. B2B software
    "best CRM for a small real estate agency",
    # 7. Legal advice
    "como processar uma companhia aérea por atraso de voo",
    # 8. Event discovery
    "music festivals happening in berlin this summer",
    # 9. DIY / Home Improvement
    "how to fix a leaky faucet in the kitchen",
    # 10. Financial advice
    "melhores investimentos de renda fixa para 2026",
    # 11. Educational
    "where can I learn python for data science for free",
    # 12. Recipe / Cooking
    "authentic italian carbonara recipe without cream",
    # 13. Travel recommendations
    "top things to do in kyoto during autumn",
    # 14. B2C Product (E-commerce allowed here since it's a product)
    "best noise cancelling headphones under $100",
    # 15. Official documentation
    "how to renew a US passport online",
    # 16. History/Fact
    "who won the battle of waterloo and why",
    # 17. Real Estate
    "comprar apartamento em moema são paulo",
    # 18. Fitness
    "best workout routine for building muscle mass in 3 months",
    # 19. Auto repair
    "car makes a squeaking noise when braking",
    # 20. Entertainment
    "when is the next season of stranger things coming out"
]

async def main():
    md_content = "# 20 Query Intent Disambiguation Test\n\n"
    md_content += "This document analyzes how the Query Rewriter transforms 20 diverse queries and what types of sources Tavily returns.\n\n"

    for i, q in enumerate(QUERIES, 1):
        print(f"Processing {i}/20: {q}")
        rewritten = await rewrite_query(q, [])
        results, _ = await search_web_async(rewritten, max_results=3)
        
        md_content += f"## {i}. Original Query: `{q}`\n"
        md_content += f"**Rewritten Query:** `{rewritten}`\n\n"
        md_content += "**Top Search Results:**\n"
        if not results:
            md_content += "- *No results found*\n"
        for r in results:
            md_content += f"- [{r.title}]({r.url})\n"
        md_content += "\n---\n"
        
        # Write to file incrementally to be safe
        with open("test_results.md", "w", encoding="utf-8") as f:
            f.write(md_content)
            
        await asyncio.sleep(1.0) # rate limit protection

if __name__ == "__main__":
    asyncio.run(main())
