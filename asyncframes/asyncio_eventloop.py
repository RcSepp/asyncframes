# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import asyncio
import asyncframes


class EventLoop(asyncframes.AbstractEventLoop):
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

    def _invoke(self, event, delay):
        if delay <= 0:
            self.loop.call_soon_threadsafe(self.sendevent, event)
        else:
            self.loop.call_soon_threadsafe(self.loop.call_later, delay, self.sendevent, event)
