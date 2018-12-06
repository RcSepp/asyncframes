# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import time
from asyncframes import Frame, PFrame, sleep, get_current_eventloop_index
from asyncframes.asyncio_eventloop import EventLoop

DEBUG_EVENTLOOP_AFFINITY = False

@PFrame
async def counter(c):
    if DEBUG_EVENTLOOP_AFFINITY: print('counter', c + ':', get_current_eventloop_index())
    await sleep()
    if DEBUG_EVENTLOOP_AFFINITY: print('counter', c + ':', get_current_eventloop_index())
    for i in range(4):
        time.sleep(1)
        if DEBUG_EVENTLOOP_AFFINITY: print('counter', c + ':', get_current_eventloop_index())
        print(c)

@Frame
async def main_frame():
    if DEBUG_EVENTLOOP_AFFINITY: print('main_frame:', get_current_eventloop_index())
    a = counter('a') # Start counter 'a'
    await sleep(0.5) # Wait 0.5 seconds
    if DEBUG_EVENTLOOP_AFFINITY: print('main_frame:', get_current_eventloop_index())
    b = counter('b') # Start counter 'b'
    await (a & b) # Wait until both counters finish
    if DEBUG_EVENTLOOP_AFFINITY: print('main_frame:', get_current_eventloop_index())

loop = EventLoop()
loop.run(main_frame)
