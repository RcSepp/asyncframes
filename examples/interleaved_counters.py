# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from asyncframes import Frame, sleep
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def counter(c):
    for i in range(5):
        await sleep(1)
        print(c)

@Frame
async def main_frame():
    a = counter('a') # Start counter 'a'
    await sleep(0.5) # Wait 0.5 seconds
    b = counter('b') # Start counter 'b'
    await (a & b) # Wait until both counters finish

loop = EventLoop()
loop.run(main_frame)
