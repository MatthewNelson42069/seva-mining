"""
Shared test fixtures for scheduler tests.

Phase 11 Wave 0: adds fake_imagen_client and fake_r2_client fixtures
for use in test_image_render.py once Plan 11-02 un-skips those tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def fake_imagen_client():
    """Mock google.genai.Client returning fixed PNG bytes."""
    client = MagicMock()
    fake_image = MagicMock()
    fake_image.image.image_bytes = b"\x89PNG\r\n\x1a\nFAKE"
    response = MagicMock()
    response.generated_images = [fake_image]
    client.aio.models.generate_images = AsyncMock(return_value=response)
    return client


@pytest.fixture
def fake_r2_client():
    """Mock aioboto3 S3 client context manager — records put_object calls."""
    s3 = AsyncMock()
    s3.put_object = AsyncMock(return_value={})
    session = MagicMock()
    session.client.return_value.__aenter__ = AsyncMock(return_value=s3)
    session.client.return_value.__aexit__ = AsyncMock(return_value=None)
    return session, s3
