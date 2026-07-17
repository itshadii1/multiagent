from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    tavily_api_key: str

    # Groq speaks the OpenAI protocol, so the stock openai SDK works unchanged.
    #
    # Chosen by measurement, on two axes that both bind:
    #
    # 1. tool-call reliability. NOT llama-3.3-70b — against the search schema it
    #    emitted a malformed call (`<function=web_search={...}</function>`) 7
    #    times in 8, which Groq rejects as `tool_use_failed`. gpt-oss-120b,
    #    llama-4-scout and qwen3-32b each went 8/8.
    # 2. tokens per minute. The free tier's real cap is TPM, not RPM (which is a
    #    roomy 1000). Measured: scout 30k, llama-3.3-70b 12k, gpt-oss-120b 8k,
    #    qwen3-32b 6k. A researcher turn carrying search results runs ~9k tokens,
    #    so anything under ~12k rejects a *single* request with a 413.
    #
    # Scout is the only free model that clears both bars. Re-measure both before
    # switching — passing one and failing the other is what makes this subtle.
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    base_url: str = "https://api.groq.com/openai/v1"

    # Agents loop until they stop calling tools; this bounds a runaway loop.
    max_tool_turns: int = 6

    # Groq's free tier caps requests per minute. Researchers fan out in
    # parallel, so cap concurrency and retry rather than stampede into a 429.
    max_concurrent_researchers: int = 3
    max_rate_limit_retries: int = 4

    # How many times the critic may send the report back. The critic can always
    # find something; the graph decides when to stop paying for it.
    max_revisions: int = 2

    # LLM-as-judge coverage check. Costs a call; the rule-based checks don't.
    use_llm_judge: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
