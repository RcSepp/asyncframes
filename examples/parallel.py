# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import time
import asyncframes
from asyncframes.asyncio_eventloop import EventLoop

@asyncframes.Frame
async def frame_counter(delay, printfunc, printfunc_args):
    time.sleep(delay)
    for _ in range(3):
        time.sleep(0.3)
        print(printfunc(*printfunc_args), end='', flush=True)

@asyncframes.PFrame
async def pframe_counter(delay, printfunc, printfunc_args):
    time.sleep(delay)
    for _ in range(3):
        time.sleep(0.3)
        print(printfunc(*printfunc_args), end='', flush=True)

@asyncframes.Frame
async def count_using_frames(printfunc):
    counters = [frame_counter(delay=0.1 * i, printfunc=printfunc, printfunc_args=(i,)) for i in range(3)]
    await asyncframes.all_(*counters)
    print()

@asyncframes.Frame
async def count_using_pframes(printfunc):
    counters = [pframe_counter(delay=0.1 * i, printfunc=printfunc, printfunc_args=(i,)) for i in range(3)]
    await asyncframes.all_(*counters)
    print()

if __name__ == "__main__":
    loop = EventLoop()

    alphabetical = lambda i: "abc"[i]
    thread_numbers = lambda i: asyncframes.get_current_eventloop_index()

    print("Run 3 blocking threads in parallel using Frames:")
    loop.run(count_using_frames, printfunc=alphabetical)
    loop.run(count_using_frames, printfunc=thread_numbers)
    print()

    print("Run 3 blocking threads in parallel using PFrames:")
    loop.run(count_using_pframes, printfunc=alphabetical)
    loop.run(count_using_pframes, printfunc=thread_numbers)
    print()

    print("Run 3 blocking threads in parallel using PFrames with 3 threads:")
    loop.run(count_using_pframes, printfunc=alphabetical, num_threads=3)
    loop.run(count_using_pframes, printfunc=thread_numbers, num_threads=3)
    print()
