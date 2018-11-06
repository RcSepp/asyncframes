# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import asyncio
import asyncframes


class EventLoop(asyncframes.AbstractEventLoop):
    """An implementation of AbstractEventLoop based on asyncio."""

    def __init__(self):
        super().__init__()
        try:
            self.loop = asyncio.get_event_loop() # Use existing eventloop
        except RuntimeError: # If no eventloop exists on this thread, ...
            self.loop = asyncio.new_event_loop() # Create a new eventloop
            asyncio.set_event_loop(self.loop) # Make the new eventloop current

    def _run(self):
        self.loop.run_forever()

    def _stop(self):
        self.loop.stop()

    def _close(self):
        self.loop.close()

    def _clear(self):
        # Re-open asyncio eventloop to discard any pending events
        self.loop.close() # Close current event loop
        self.loop = asyncio.new_event_loop() # Create a new eventloop
        asyncio.set_event_loop(self.loop) # Make the new eventloop current

    def _post(self, delay, callback, args):
        if not self.loop.is_closed():
            if delay <= 0:
                self.loop.call_soon(callback, *args)
            else:
                self.loop.call_later(delay, callback, *args)

    def _invoke(self, delay, callback, args):
        if not self.loop.is_closed():
            if delay <= 0:
                self.loop.call_soon_threadsafe(callback, *args)
            else:
                self.loop.call_soon_threadsafe(self.loop.call_later, delay, callback, *args)
