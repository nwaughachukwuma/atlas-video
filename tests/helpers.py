# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_asyncio_run(return_value=None, side_effect=None):
    """Create a mock for asyncio.run that properly handles coroutines.

    When asyncio.run is mocked, the coroutine passed to it is never awaited,
    causing RuntimeWarning. This helper consumes the coroutine to prevent warnings.
    """

    def _run_mock(coro):
        # Close the coroutine to prevent "never awaited" warnings
        if hasattr(coro, "close"):
            coro.close()
        if side_effect:
            if isinstance(side_effect, Exception):
                raise side_effect
            return side_effect
        return return_value

    return _run_mock
