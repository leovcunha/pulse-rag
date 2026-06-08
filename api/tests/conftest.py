import pytest

@pytest.fixture(autouse=True)
def reset_sse_starlette_exit_event():
    import sse_starlette.sse
    sse_starlette.sse.AppStatus.should_exit_event = None
    yield
    sse_starlette.sse.AppStatus.should_exit_event = None
