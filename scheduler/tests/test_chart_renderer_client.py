"""
Tests for scheduler/agents/chart_renderer_client.py — Python asyncio subprocess wrapper.

Tests mock asyncio.create_subprocess_exec to avoid requiring Node.js in the test environment.
All tests are runnable with: cd scheduler && uv run pytest tests/test_chart_renderer_client.py -x
"""
import asyncio
import base64
import json
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")


def make_fake_proc(responses=None):
    """Create a fake subprocess mock with stdin/stdout/stderr.

    responses: list of bytes to return from stdout.readline() in order.
    """
    responses = responses or []
    response_iter = iter(responses)

    proc = MagicMock()
    proc.returncode = None  # Still running
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.stderr = MagicMock()
    proc.terminate = MagicMock()
    proc.wait = AsyncMock()

    async def readline_side_effect():
        try:
            return next(response_iter)
        except StopIteration:
            return b''

    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock(side_effect=readline_side_effect)

    return proc


def make_png_response(png_bytes=b'PNGBYTES'):
    """Make a valid png_b64 response bytes line."""
    b64 = base64.b64encode(png_bytes).decode()
    return (json.dumps({"png_b64": b64}) + '\n').encode()


def make_error_response(message='render failed'):
    """Make an error response bytes line."""
    return (json.dumps({"error": message}) + '\n').encode()


# ---------------------------------------------------------------------------
# test_render_charts_sends_json_and_reads_response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_render_charts_sends_json_and_reads_response():
    """render_charts() writes JSON lines to stdin and reads base64-PNG response; returns list[bytes]."""
    from agents.chart_renderer_client import ChartRendererClient
    from models.chart_spec import BundleCharts, ChartSpec, ChartType

    fake_proc = make_fake_proc([make_png_response(b'PNG1')])

    with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=fake_proc)):
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        await client.start()

        spec = ChartSpec(type=ChartType.bar, title='Gold Price')
        payload = BundleCharts(charts=[spec], twitter_caption='Test caption')
        result = await client.render_charts(payload)

    assert len(result) == 1
    assert result[0] == b'PNG1'
    fake_proc.stdin.write.assert_called_once()
    written = fake_proc.stdin.write.call_args[0][0]
    parsed = json.loads(written.decode().strip())
    assert parsed['type'] == 'bar'
    assert parsed['title'] == 'Gold Price'


# ---------------------------------------------------------------------------
# test_render_charts_two_specs_returns_two_pngs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_render_charts_two_specs_returns_two_pngs():
    """payload with charts=[spec1,spec2] returns list of 2 bytes objects."""
    from agents.chart_renderer_client import ChartRendererClient
    from models.chart_spec import BundleCharts, ChartSpec, ChartType

    fake_proc = make_fake_proc([
        make_png_response(b'PNG1'),
        make_png_response(b'PNG2'),
    ])

    with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=fake_proc)):
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        await client.start()

        spec1 = ChartSpec(type=ChartType.bar, title='Chart 1')
        spec2 = ChartSpec(type=ChartType.line, title='Chart 2')
        payload = BundleCharts(charts=[spec1, spec2], twitter_caption='Caption')
        result = await client.render_charts(payload)

    assert len(result) == 2
    assert result[0] == b'PNG1'
    assert result[1] == b'PNG2'
    assert fake_proc.stdin.write.call_count == 2


# ---------------------------------------------------------------------------
# test_render_charts_error_response_returns_none_for_that_chart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_render_charts_error_response_returns_none_for_that_chart():
    """Node responds with error for one chart; that chart returns None; other charts return bytes."""
    from agents.chart_renderer_client import ChartRendererClient
    from models.chart_spec import BundleCharts, ChartSpec, ChartType

    fake_proc = make_fake_proc([
        make_error_response('unknown chart type'),
        make_png_response(b'PNG2'),
    ])

    with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=fake_proc)):
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        await client.start()

        spec1 = ChartSpec(type=ChartType.bar, title='Chart 1')
        spec2 = ChartSpec(type=ChartType.line, title='Chart 2')
        payload = BundleCharts(charts=[spec1, spec2], twitter_caption='Caption')
        result = await client.render_charts(payload)

    assert result[0] is None
    assert result[1] == b'PNG2'


# ---------------------------------------------------------------------------
# test_render_charts_timeout_triggers_restart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_render_charts_timeout_triggers_restart():
    """If readline times out, method returns [None] and marks process for restart."""
    from agents.chart_renderer_client import ChartRendererClient
    from models.chart_spec import BundleCharts, ChartSpec, ChartType

    async def hang():
        await asyncio.sleep(30)
        return b''

    fake_proc = MagicMock()
    fake_proc.returncode = None
    fake_proc.stdin = MagicMock()
    fake_proc.stdin.write = MagicMock()
    fake_proc.stdin.drain = AsyncMock()
    fake_proc.stdout = MagicMock()
    fake_proc.stdout.readline = AsyncMock(side_effect=hang)
    fake_proc.terminate = MagicMock()
    fake_proc.wait = AsyncMock()

    with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=fake_proc)):
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        await client.start()

        spec = ChartSpec(type=ChartType.bar, title='Chart 1')
        payload = BundleCharts(charts=[spec], twitter_caption='Caption')

        # Use a very short timeout override for testing
        result = await client.render_charts(payload, timeout=0.05)

    assert result[0] is None
    assert client._proc is None  # marked for restart


# ---------------------------------------------------------------------------
# test_start_spawns_subprocess
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_spawns_subprocess():
    """client.start() spawns a Node process; client._proc is not None after start()."""
    from agents.chart_renderer_client import ChartRendererClient

    fake_proc = make_fake_proc()

    with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=fake_proc)) as mock_exec:
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        assert client._proc is None
        await client.start()
        assert client._proc is not None
        mock_exec.assert_called_once()


# ---------------------------------------------------------------------------
# test_stop_terminates_process
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_terminates_process():
    """client.stop() calls proc.terminate() if process is running."""
    from agents.chart_renderer_client import ChartRendererClient

    fake_proc = make_fake_proc()

    with patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=fake_proc)):
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        await client.start()
        await client.stop()

    fake_proc.terminate.assert_called_once()
    fake_proc.wait.assert_called_once()


# ---------------------------------------------------------------------------
# test_restart_on_dead_process
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restart_on_dead_process():
    """If _proc.returncode is not None (crashed), next render_charts() spawns a new process."""
    from agents.chart_renderer_client import ChartRendererClient
    from models.chart_spec import BundleCharts, ChartSpec, ChartType

    dead_proc = make_fake_proc()
    dead_proc.returncode = 1  # Simulate crash

    new_proc = make_fake_proc([make_png_response(b'PNG1')])

    call_count = [0]

    async def mock_exec(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return dead_proc
        return new_proc

    with patch('asyncio.create_subprocess_exec', side_effect=mock_exec):
        client = ChartRendererClient(renderer_path='/fake/render-chart.js')
        await client.start()  # First spawn (dead_proc)
        assert client._proc.returncode == 1

        spec = ChartSpec(type=ChartType.bar, title='Chart')
        payload = BundleCharts(charts=[spec], twitter_caption='Caption')
        result = await client.render_charts(payload)  # Should restart

    assert call_count[0] == 2  # Two subprocess spawns: initial + restart
    assert result[0] == b'PNG1'
