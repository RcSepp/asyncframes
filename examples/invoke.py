# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import threading
import time
from asyncframes import Frame, EventSource, sleep
from asyncframes.pyqt5_eventloop import EventLoop

class Thread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = EventSource('Thread.event')
    def run(self):
        time.sleep(1)
        self.event.invoke(self)

@Frame
async def print_dots():
    while True:
        await sleep(0.1)
        print(".", end="")

@Frame
async def main_frame():
    print("start")
    t = Thread()
    t.start()
    print_dots()
    await t.event
    print("done")

loop = EventLoop()
loop.run(main_frame)
