=========================================================
asyncframes - Parallel programming for software engineers
=========================================================

|travis_badge| |readthedocs_badge|

Code repository: https://github.com/RcSepp/asyncframes

Python Package Index: https://pypi.org/project/asyncframes/

----

*asyncframes* is a coroutine library for Python and a reference implementation of the *Frame Hierarchy Programming Model* (FHM). The goal of FHM is to help programmers design clean and scalable parallel programs.
The main features of *asyncframes* are:

- Hierarchical code design
- Inherent and scalable parallelism
- Architecture independence
- Extensibility through frame classes (a class whose lifetime is bound to the execution of a frame)


Introduction
============

In the *Frame Hierarchy Programming Model* (FHM) a program is represented as a dynamic tree of *frames*. A frame is a suspendable function (a coroutine) with an object oriented context (the frame class) that only exists until the function returns. Frames can be used to represent both temporal processes (using the coroutine) and physical or conceptual objects (using the frame class).

Each FHM program has exactly one root frame. The root frame can recursively spawn child frames. Each child frame runs in parallel unless it's awaiting another frame or an awaitable event. Frames of type ``Frame`` run on a single thread. They use cooperative multitasking to simulate parallelism. Frames of type ``PFrame`` run on any of the threads available in the event loop's thread pool. ``Frame`` and ``PFrame`` are frame classes. They can be sub-classed to create specialized frame classes with encapsulated data.

Installation
============

*asyncframes* can be installed via `pip`: ::

    pip install asyncframes

*asyncframes* requires an event loop to suspend execution without blocking the operating system. The default event loop is ``asyncframes.asyncio_eventloop.EventLoop``. It doesn't depend on any Python packages besides the builtin *asyncio* package.
Some frameworks, like Qt, use their own event loops. When using such frameworks, the framework's event loop should be reused for *asyncframes* by implementing the ``asyncframes.AbstractEventLoop`` interface.


Examples
========

Here is a minimal example of using *asyncframes*: ::

    from asyncframes import Frame
    from asyncframes.asyncio_eventloop import EventLoop

    @Frame
    async def main_frame():
        print("Hello World!")

    loop = EventLoop()
    loop.run(main_frame)

Here is an example of suspending a frame: ::

    from asyncframes import Frame, sleep
    from asyncframes.asyncio_eventloop import EventLoop

    @Frame
    async def main_frame():
        for i in range(5):
            await sleep(1)
            print(i + 1)

    loop = EventLoop()
    loop.run(main_frame)

Here is an example of running two frames in parallel: ::

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

Here is an example of running two blocking operations in parallel: ::

    import time
    from asyncframes import Frame, PFrame, sleep
    from asyncframes.asyncio_eventloop import EventLoop

    @PFrame
    async def counter(c):
        for i in range(5):
            time.sleep(1)
            print(c)

    @Frame
    async def main_frame():
        a = counter('a') # Start counter 'a'
        await sleep(0.5) # Wait 0.5 seconds
        b = counter('b') # Start counter 'b'
        await (a & b) # Wait until both counters finish

    loop = EventLoop()
    loop.run(main_frame)
