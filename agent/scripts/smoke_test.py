import os
import sys
from core.config import load_config
from core.llm import NebiusClient

def main():
    api_key = os.environ.get("NEBIUS_API_KEY")
    try:
        config = load_config("config.json")
        client = NebiusClient(config["nebius"]["base_url"], api_key)
        model = config["models"]["classifier"]
        res = client.chat(model, [{"role": "user", "content": "Reply with exactly: OK"}])
        print(f"NEBIUS: OK tokens={res.total_tokens}")
    except Exception as e:
        clean_err = str(e).replace(api_key or "", "[REDACTED]") if api_key else str(e)
        print(f"NEBIUS FAILED: {type(e).__name__} - {clean_err}")

    try:
        from tavily import TavilyClient
        tavily_key = os.environ.get("TAVILY_API_KEY")
        tavily = TavilyClient(api_key=tavily_key)
        res = tavily.search(query="test", max_results=1)
        results_count = len(res.get("results", []))
        print(f"TAVILY: OK results={results_count}")
    except Exception as e:
        tavily_key = os.environ.get("TAVILY_API_KEY")
        clean_err = str(e).replace(tavily_key or "", "[REDACTED]") if tavily_key else str(e)
        print(f"TAVILY FAILED: {type(e).__name__} - {clean_err}")

if __name__ == "__main__":
    main()