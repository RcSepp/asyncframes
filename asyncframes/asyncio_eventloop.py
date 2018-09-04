import asyncio
import asyncframes


class EventLoop(asyncframes.EventLoop):
    def __init__(self):
        super().__init__()
        self.loop = asyncio.get_event_loop()

    def _run(self):
        self.loop.run_forever()

    def _stop(self):
        self.loop.stop()

    def _post(self, event, delay):
        if delay <= 0:
            self.loop.call_soon(self.sendevent, event)
        else:
            self.loop.call_later(delay, self.sendevent, event)
