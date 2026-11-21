"""Let ASGI contract tests run without loopback sockets in a restricted Windows session."""

import asyncio
import os
import selectors
from threading import Event


class InMemorySelector(selectors.BaseSelector):
    def __init__(self):
        self.ready = Event()

    def get_map(self):
        return {}

    def register(self, fileobj, events, data=None):
        raise RuntimeError('The in-memory ASGI test loop does not register sockets')

    def unregister(self, fileobj):
        raise KeyError(fileobj)

    def select(self, timeout=None):
        self.ready.wait(timeout)
        self.ready.clear()
        return []


class InMemoryLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__(selector=InMemorySelector())

    def _make_self_pipe(self):
        pass

    def _close_self_pipe(self):
        pass

    def _write_to_self(self):
        self._selector.ready.set()


class InMemoryPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        return InMemoryLoop()


def enable_for_restricted_windows():
    if os.environ.get('SMARTLIB_TEST_NO_SOCKETS') == '1':
        asyncio.set_event_loop_policy(InMemoryPolicy())
