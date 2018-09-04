# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from asyncframes import Frame, sleep
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def main_frame():
    for i in range(5):
        await sleep(1)
        print(i + 1)

loop = EventLoop()
loop.run(main_frame)
