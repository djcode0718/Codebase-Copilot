"""
Benchmark script to trace and measure full request lifecycle of chat queries:
1. hi
2. What is this repository about?
3. Where is the main application entry point?
4. How does authentication work?
"""
import asyncio
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

from api.services.chat_service import stream_chat_response
from api.services.chat_stream_utils import parse_sse_data_line


async def run_query_test(query: str, index_name: str = "Codebase-Copilot"):
    print(f"\n=======================================================")
    print(f"TESTING QUERY: '{query}'")
    print(f"=======================================================")

    t0 = time.time()
    first_token_time = None
    tokens = []
    metadata = {}
    suggestions = []
    event_types = []

    try:
        async for sse_line in stream_chat_response(
            query=query,
            index_name=index_name,
            repo_id="benchmark-test-repo",
            chat_id=f"bench-{int(time.time()*1000)}",
        ):
            parsed = parse_sse_data_line(sse_line)
            if not parsed:
                continue

            etype = parsed.get("type")
            event_types.append(etype)

            if etype == "token":
                if first_token_time is None:
                    first_token_time = time.time() - t0
                tokens.append(parsed.get("content", ""))
            elif etype == "metadata":
                metadata = parsed
            elif etype == "suggestions":
                suggestions = parsed.get("questions", [])

        total_time = time.time() - t0
        full_text = "".join(tokens)

        # Print summary
        query_mode = metadata.get("query_mode", "N/A (early exit)" if not metadata else "unknown")
        retrieved_files = metadata.get("retrieved_files", [])
        num_retrieved = len(retrieved_files)
        retrieval_ms = metadata.get("latency_retrieval_ms", 0)
        llm_ms = metadata.get("latency_llm_ms", 0)
        provider = metadata.get("llm_provider", "deterministic" if not metadata.get("llm_provider") else metadata.get("llm_provider"))
        model = metadata.get("llm_model", "deterministic" if not metadata.get("llm_model") else metadata.get("llm_model"))
        sse_done = "done" in event_types

        print(f"Classification:         {query_mode}")
        print(f"Retrieval Triggered:    {'YES' if num_retrieved > 0 else 'NO'}")
        print(f"Retrieved Chunks:       {num_retrieved}")
        print(f"Retrieval Latency (ms): {retrieval_ms}")
        print(f"LLM Provider / Model:   {provider} / {model}")
        print(f"Time to First Token:    {first_token_time:.3f}s" if first_token_time else "Time to First Token:    N/A")
        print(f"Total Response Time:    {total_time:.3f}s")
        print(f"SSE Completed:          {'YES' if sse_done else 'NO'} (events: {set(event_types)})")
        print(f"Response Preview:       {full_text[:180]}...")
        if suggestions:
            print(f"Followup Suggestions:   {suggestions[:2]}")

        return {
            "query": query,
            "query_mode": query_mode,
            "retrieval_triggered": num_retrieved > 0,
            "num_chunks": num_retrieved,
            "retrieval_ms": retrieval_ms,
            "provider": provider,
            "model": model,
            "time_to_first_token_s": round(first_token_time, 3) if first_token_time else 0,
            "total_time_s": round(total_time, 3),
            "sse_done": sse_done,
            "preview": full_text[:120].strip()
        }

    except Exception as e:
        print(f"FAILED: {e}")
        return {"query": query, "error": str(e)}


async def main():
    queries = [
        "hi",
        "What is this repository about?",
        "Where is the main application entry point?",
        "How does authentication work?"
    ]
    results = []
    for q in queries:
        res = await run_query_test(q)
        results.append(res)

    print("\n\n==================== FINAL BENCHMARK SUMMARY ====================")
    print(f"{'Query':<40} | {'Mode':<12} | {'Chunks':<6} | {'TTFT (s)':<8} | {'Total (s)':<9} | {'SSE'}")
    print("-" * 90)
    for r in results:
        if "error" in r:
            print(f"{r['query']:<40} | ERROR: {r['error']}")
        else:
            print(f"{r['query']:<40} | {r['query_mode']:<12} | {r['num_chunks']:<6} | {r['time_to_first_token_s']:<8} | {r['total_time_s']:<9} | {'PASS' if r['sse_done'] else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
