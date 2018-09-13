# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from asyncframes import Frame, EventSource, sleep
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def progress_reporter(self):
    # Initialize frame
    self.progress = EventSource(self.__name__ + ".progress")

    # Report progress
    event = await (self.free | self.progress)
    while event.source != self.free:
        progress_value = max(0, min(100, event.args))
        print("progress: %f" % progress_value)

        if progress_value == 100:
            break

        event = await (self.free | self.progress)

    # Free frame
    print("process canceled" if event.source == self.free else "process finished")

@Frame
async def main_frame(self):
    pr = progress_reporter()
    for progress in range(0, 100, 13):
        pr.progress.post(self, progress)
        if progress > 20:
            return
        await sleep(1)
    pr.progress.post(self, 100)
    await pr

loop = EventLoop()
loop.run(main_frame)
