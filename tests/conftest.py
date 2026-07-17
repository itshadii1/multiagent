"""Test-wide setup.

Placeholder keys so `get_settings()` validates: the graph reads config for
things like the revision cap, and that must not make the orchestration tests
require real credentials. Nothing here ever reaches the network — the agents
are faked in the tests that touch them.
"""

import os

import pytest

from research_agents.config import get_settings


@pytest.fixture(autouse=True, scope="session")
def _fake_keys():
    os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
    os.environ.setdefault("TAVILY_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
