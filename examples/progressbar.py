# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import signal
from asyncframes import Frame, EventSource, sleep
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def progress_reporter(self, title):
    def create_progress_str(progress_value):
        prefix = "{}    [".format(title)
        postfix = "] {}%".format(str(progress_value).rjust(3))
        progressbar_length = 80 - len(prefix) - len(postfix)
        progress_length = progress_value * progressbar_length // 100
        return "\r" + prefix + '#' * progress_length + '-' * (progressbar_length - progress_length) + postfix

    # Initialize frame
    self.progress = EventSource(self.__name__ + ".progress")
    print(create_progress_str(0), end="")

    # Report progress
    event = await (self.free | self.progress)
    while event.source != self.free:
        progress_value = max(0, min(100, event.args))
        print(create_progress_str(progress_value), end="")

        if progress_value == 100:
            # Cleanup after finished process
            print("")
            return

        event = await (self.free | self.progress)

    # Cleanup after aborted process
    print("")
    print("process aborted")

@Frame
async def process(self, pr):
    for progress in range(0, 100, 13):
        await sleep(1)
        pr.progress.post(self, progress)
    await sleep(1)
    pr.progress.post(self, 100)

@Frame
async def sigint_listener(self):
    # Register a custom handler for the SIGINT signal
    sigint = EventSource('sigint')
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda s, f: sigint.post(None))

    # Wait until either the SIGINT signal was fired or this frame was manually removed
    await (self.free | sigint)

    # Restore original SIGINT handler
    signal.signal(signal.SIGINT, original_sigint_handler)
    return 'sigint received!'

@Frame
async def main_frame(self):
    sl = sigint_listener()
    pr = progress_reporter('Running Process')
    p = process(pr)
    await (pr | sl)

loop = EventLoop()
loop.run(main_frame)
