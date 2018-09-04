# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from asyncframes import Frame
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def main_frame():
    print("Hello World!")

loop = EventLoop()
loop.run(main_frame)
