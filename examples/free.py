# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from asyncframes import Frame, Event, sleep
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def progress_reporter(self):
    # Initialize frame
    self.progress = Event(self.__name__ + ".progress")

    # Report progress
    event, progress_value = await (self.free | self.progress)
    while event != self.free:
        progress_value = max(0, min(100, progress_value))
        print("progress: %f" % progress_value)

        if progress_value == 100:
            break

        event, progress_value = await (self.free | self.progress)

    # Free frame
    print("process canceled" if event == self.free else "process finished")

@Frame
async def main_frame():
    pr = progress_reporter()
    await pr.ready
    for progress in range(0, 100, 13):
        pr.progress.post(progress)
        if progress > 20:
            return
        await sleep(1)
    pr.progress.post(100)
    await pr

loop = EventLoop()
loop.run(main_frame)
