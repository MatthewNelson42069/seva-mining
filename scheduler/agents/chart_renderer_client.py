"""
ChartRendererClient — manages the persistent Node.js chart renderer subprocess.

Protocol: one JSON line per chart spec written to stdin; one JSON line (png_b64 or error)
read from stdout. The Node process is spawned once at scheduler startup and reused
across all render calls. Auto-restarts on subprocess crash.

Architecture decision (RESEARCH.md Q5):
- Long-running subprocess (Option A) chosen over separate Railway service (Option B)
  and spawn-per-render (Option C).
- Reason: no cold start per render (~400-600ms startup paid once), no extra billing,
  simpler than per-render process management.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

# Default path to render-chart.js relative to this file's location
_DEFAULT_RENDERER_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'chart_renderer', 'render-chart.js'
)


class ChartRendererClient:
    """Manages a persistent Node.js chart renderer subprocess.

    Usage:
        client = ChartRendererClient()
        await client.start()            # Call once at scheduler startup
        pngs = await client.render_charts(bundle_charts_payload)
        await client.stop()             # Call on scheduler shutdown
    """

    def __init__(self, renderer_path: str | None = None) -> None:
        self._renderer_path = renderer_path or _DEFAULT_RENDERER_PATH
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        """Spawn the Node chart renderer subprocess.

        Called once at scheduler startup. The process stays alive across all
        render calls, amortizing the ~400-600ms Node V8 + Recharts startup cost.
        """
        logger.info("ChartRendererClient: starting Node renderer at %s", self._renderer_path)
        self._proc = await asyncio.create_subprocess_exec(
            'node',
            self._renderer_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("ChartRendererClient: renderer started (pid=%s)", self._proc.pid if self._proc else None)

    async def stop(self) -> None:
        """Terminate the Node chart renderer subprocess.

        Called on scheduler shutdown. Safe to call if not started or already stopped.
        """
        if self._proc and self._proc.returncode is None:
            logger.info("ChartRendererClient: stopping renderer process")
            self._proc.terminate()
            await self._proc.wait()
            logger.info("ChartRendererClient: renderer stopped")
        self._proc = None

    async def render_charts(
        self,
        payload: "BundleCharts",  # noqa: F821 — forward ref, imported lazily
        timeout: float = 10.0,
    ) -> list[bytes | None]:
        """Render all charts in a BundleCharts payload.

        Sends one JSON line per chart spec to the Node process stdin.
        Reads one JSON response line per chart from stdout.
        Auto-restarts the process if it has crashed.

        Args:
            payload: BundleCharts instance with 1-2 ChartSpec items.
            timeout: Seconds to wait for each chart response. Default 10s.

        Returns:
            list[bytes | None] — one entry per chart in payload.charts.
            None for a chart that failed (error response or timeout).
            bytes (PNG) for a chart that rendered successfully.
        """
        # Lazy import to avoid circular imports at module load time
        from models.chart_spec import BundleCharts  # noqa: PLC0415

        # Ensure process is alive; restart if crashed
        if self._proc is None or self._proc.returncode is not None:
            logger.warning("ChartRendererClient: process is not running — restarting")
            await self.start()

        results: list[bytes | None] = []

        for spec in payload.charts:
            spec_json = json.dumps(spec.model_dump(mode='json')) + '\n'
            self._proc.stdin.write(spec_json.encode())  # type: ignore[union-attr]

            try:
                await self._proc.stdin.drain()  # type: ignore[union-attr]
            except Exception as exc:
                logger.error("ChartRendererClient: stdin drain failed: %s", exc)
                results.append(None)
                self._proc = None  # Mark for restart
                continue

            try:
                line = await asyncio.wait_for(
                    self._proc.stdout.readline(),  # type: ignore[union-attr]
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "ChartRendererClient: timeout waiting for chart '%s' response — marking for restart",
                    spec.title[:60],
                )
                self._proc = None  # Mark for restart on next call
                results.append(None)
                continue
            except Exception as exc:
                logger.error("ChartRendererClient: stdout readline error: %s", exc)
                self._proc = None
                results.append(None)
                continue

            if not line:
                logger.error("ChartRendererClient: empty response for chart '%s'", spec.title[:60])
                results.append(None)
                continue

            try:
                response = json.loads(line.decode().strip())
            except json.JSONDecodeError as exc:
                logger.error("ChartRendererClient: invalid JSON response: %s — raw: %r", exc, line[:200])
                results.append(None)
                continue

            if 'error' in response:
                logger.warning(
                    "ChartRendererClient: renderer error for chart '%s': %s",
                    spec.title[:60],
                    response['error'],
                )
                results.append(None)
                continue

            png_b64 = response.get('png_b64', '')
            if not png_b64:
                logger.error("ChartRendererClient: empty png_b64 in response for chart '%s'", spec.title[:60])
                results.append(None)
                continue

            try:
                png_bytes = base64.b64decode(png_b64)
                results.append(png_bytes)
            except Exception as exc:
                logger.error("ChartRendererClient: base64 decode failed: %s", exc)
                results.append(None)

        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_client: ChartRendererClient | None = None


def get_chart_renderer_client() -> ChartRendererClient:
    """Return the module-level singleton ChartRendererClient.

    Creates a new instance if not yet initialized.
    The singleton is started by worker.py at scheduler startup.
    """
    global _client
    if _client is None:
        _client = ChartRendererClient()
    return _client


async def render_infographic(bundle_charts_json: str) -> list[bytes | None]:
    """Module-level helper: validate BundleCharts JSON and render all charts.

    Args:
        bundle_charts_json: JSON string matching BundleCharts schema.

    Returns:
        list[bytes | None] — PNG bytes per chart, None for failures.
    """
    from models.chart_spec import BundleCharts  # noqa: PLC0415
    payload = BundleCharts.model_validate_json(bundle_charts_json)
    return await get_chart_renderer_client().render_charts(payload)
