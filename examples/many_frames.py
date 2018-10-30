# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import time
from asyncframes import Frame, PFrame, sleep, all_
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def main_frame():
    subframes = [sub_frame(i) for i in range(10000)]
    print(sum(1 if result == True else 0 for result in await all_(*subframes)))

@PFrame
async def sub_frame(i):
    time.sleep(0.001)
    return i % 2 == 0

loop = EventLoop()
loop.run(main_frame)
