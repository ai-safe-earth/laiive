"""
API connectivity tests for all LLM endpoints.
Run with: pytest tests/test_llm_api.py -v --timeout=60

These tests verify that external LLM services are:
1. Reachable
2. Responding within timeout
3. Returning expected format
"""

import pytest
import time
import httpx
from openai import OpenAI
from config import settings

# Mark all tests as integration (skip in CI with: pytest -m "not integration")
pytestmark = pytest.mark.integration


class TestOpenAIChat:
    """Test OpenAI Chat Completions API."""

    @pytest.fixture
    def client(self):
        return OpenAI(
            api_key=settings.openai_api_key,
            http_client=httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)),
        )

    def test_openai_chat_connectivity(self, client):
        """Verify OpenAI chat API is reachable."""
        start = time.time()
        response = client.chat.completions.create(
            model=settings.composer_model,
            messages=[{"role": "user", "content": "Say 'ok'"}],
            max_tokens=5,
        )
        elapsed = time.time() - start

        assert response.choices[0].message.content is not None
        assert elapsed < 30, f"OpenAI took {elapsed:.1f}s"
        print(f"✓ OpenAI Chat responded in {elapsed:.2f}s")

    def test_openai_chat_token_usage(self, client):
        """Verify token usage is returned (needed for metrics)."""
        response = client.chat.completions.create(
            model=settings.composer_model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
        )

        assert hasattr(response, "usage")
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        print(
            f"✓ Tokens: {response.usage.prompt_tokens} in, {response.usage.completion_tokens} out"
        )

    def test_query_builder_model(self, client):
        """Test the model used for query building."""
        response = client.chat.completions.create(
            model=settings.query_builder_model,
            messages=[{"role": "user", "content": "Respond with: MATCH (n) RETURN n"}],
            max_tokens=20,
        )
        assert response.choices[0].message.content is not None
        print(f"✓ Query builder model ({settings.query_builder_model}) works")


class TestOpenAIEmbeddings:
    """Test OpenAI Embeddings API."""

    @pytest.fixture
    def client(self):
        return OpenAI(
            api_key=settings.openai_api_key,
            http_client=httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)),
        )

    def test_embeddings_connectivity(self, client):
        """Verify embeddings API is reachable."""
        start = time.time()
        response = client.embeddings.create(
            model=settings.embeddings_model,
            input="Test embedding",
        )
        elapsed = time.time() - start

        assert len(response.data) > 0
        assert len(response.data[0].embedding) > 0
        assert elapsed < 30, f"Embeddings took {elapsed:.1f}s"
        print(f"✓ Embeddings responded in {elapsed:.2f}s")

    def test_embeddings_dimension(self, client):
        """Verify embedding dimensions are correct."""
        response = client.embeddings.create(
            model=settings.embeddings_model,
            input="Jazz concert in Berlin",
        )

        embedding = response.data[0].embedding
        # text-embedding-3-small returns 1536 dimensions
        assert len(embedding) == 1536, f"Expected 1536 dims, got {len(embedding)}"
        print(f"✓ Embedding dimension: {len(embedding)}")

    def test_batch_embeddings(self, client):
        """Test batch embedding (used for multiple artists)."""
        texts = ["Artist 1", "Artist 2", "Artist 3"]
        response = client.embeddings.create(
            model=settings.embeddings_model,
            input=texts,
        )

        assert len(response.data) == 3
        print(f"✓ Batch embeddings: {len(response.data)} vectors returned")


class TestOpenAIModeration:
    """Test the OpenAI moderation endpoint (free) used by the safety guard."""

    @pytest.fixture
    def client(self):
        return OpenAI(
            api_key=settings.openai_api_key,
            http_client=httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0)),
        )

    def test_moderation_safe_content(self, client):
        result = client.moderations.create(
            model="omni-moderation-latest",
            input="Find jazz concerts in Berlin this weekend",
        )
        assert result.results[0].flagged is False
        print("moderation: safe content not flagged")


class TestAllEndpointsSummary:
    """Quick health check for all endpoints."""

    def test_all_llm_endpoints(self):
        """Single test that checks all endpoints."""
        results = {}

        # OpenAI Chat
        try:
            client = OpenAI(
                api_key=settings.openai_api_key,
                http_client=httpx.Client(timeout=httpx.Timeout(15.0)),
            )
            start = time.time()
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "ok"}],
                max_tokens=1,
            )
            results["openai_chat"] = f"✓ {time.time() - start:.2f}s"
        except Exception as e:
            results["openai_chat"] = f"✗ {type(e).__name__}"

        # OpenAI Embeddings
        try:
            start = time.time()
            client.embeddings.create(model="text-embedding-3-small", input="test")
            results["openai_embeddings"] = f"✓ {time.time() - start:.2f}s"
        except Exception as e:
            results["openai_embeddings"] = f"✗ {type(e).__name__}"

        # Print summary
        print("\n" + "=" * 50)
        print("LLM API HEALTH CHECK")
        print("=" * 50)
        for endpoint, status in results.items():
            print(f"  {endpoint}: {status}")
        print("=" * 50)

        # Fail if any endpoint failed
        failures = [k for k, v in results.items() if v.startswith("✗")]
        assert not failures, f"Failed endpoints: {failures}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=60"])
