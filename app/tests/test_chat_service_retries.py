import time
import types

from app.services.chat_service import ChatService


class StubChoice:
    def __init__(self, content):
        class Msg:
            def __init__(self, c):
                self.content = c
        self.message = Msg(content)


class StubResponse:
    def __init__(self, content, total_tokens=0):
        self.choices = [StubChoice(content)]
        class Usage:
            def __init__(self, t):
                self.total_tokens = t
        self.usage = Usage(total_tokens)


class FailingThenSuccessClient:
    def __init__(self, fail_times, content='ok', tokens=42):
        self.fail_times = fail_times
        self.calls = 0
        self.content = content
        self.tokens = tokens

    class Chat:
        class Completions:
            def __init__(self, outer):
                self._outer = outer

            def create(self, **kwargs):
                self._outer.calls += 1
                if self._outer.calls <= self._outer.fail_times:
                    raise Exception("Rate limit")
                return StubResponse(self._outer.content, self._outer.tokens)

        def __init__(self, outer):
            self.completions = FailingThenSuccessClient.Chat.Completions(outer)

    def __init_subclass__(cls):
        pass

    def __post_init__(self):
        pass

    def __getattr__(self, item):
        if item == 'chat':
            return FailingThenSuccessClient.Chat(self)
        raise AttributeError(item)


def test_chat_completion_with_retries_succeeds_after_backoff(monkeypatch):
    service = ChatService()

    # Configure retries/backoff deterministically
    service.max_retries = 3
    service.backoff_base = 1.0  # 1^attempt seconds
    service.model = 'gpt-3.5-turbo'
    service.max_tokens = 10
    service.temperature = 0.0

    # Inject stub client: fail twice, succeed on third call
    stub_client = FailingThenSuccessClient(fail_times=2, content='hello', tokens=99)
    service.client = stub_client

    start = time.time()
    resp = service._chat_completion_with_retries([
        {"role": "user", "content": "ping"}
    ])
    elapsed = time.time() - start

    # Validate response and that retries happened
    assert resp.choices[0].message.content == 'hello'
    assert stub_client.calls == 3
    # With backoff_base=1 and 2 retries, elapsed should be at least ~2 seconds
    assert elapsed >= 2.0


def test_chat_completion_with_retries_raises_after_exhaustion(monkeypatch):
    service = ChatService()
    service.max_retries = 2
    service.backoff_base = 1.0
    service.model = 'gpt-3.5-turbo'
    service.max_tokens = 10
    service.temperature = 0.0

    # Fail all attempts
    stub_client = FailingThenSuccessClient(fail_times=10)
    service.client = stub_client

    try:
        service._chat_completion_with_retries([
            {"role": "user", "content": "ping"}
        ])
        assert False, "Expected exception after retries exhausted"
    except Exception as e:
        assert 'Rate limit' in str(e)
        assert stub_client.calls == service.max_retries