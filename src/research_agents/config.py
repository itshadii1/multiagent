from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    tavily_api_key: str

    # Groq speaks the OpenAI protocol, so the stock openai SDK works unchanged.
    model: str = "llama-3.3-70b-versatile"
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
