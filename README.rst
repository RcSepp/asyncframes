=====================================================
asyncframes - Object oriented coroutines for everyone
=====================================================

.. image:: https://travis-ci.org/RcSepp/asyncframes.svg?branch=master
    :target: https://travis-ci.org/RcSepp/asyncframes

Code repository: https://gitlab.com/RcSepp/asyncframes

----

*asyncframes* is a coroutine library for Python and a reference implementation
for the *Frame Hierarchy Programming Model* (FHM). The goal of FHM is to help
programmers design clean and maintainable source code. See section `Frame
Hierarchy Programming Model`_ for details.

The main features of *asyncframes* are:

- Simple syntax (compared with *asyncio*)
- Hierarchical composition of coroutines
- Creation of coroutine classes (a class whose lifetime is bound to the
  execution of a coroutine)


Introduction
============

Frame Hierarchy Programming Model
---------------------------------

In the *Frame Hierarchy Programming Model* (FHM) a program is represented as a
dynamic tree of *frames*. A frame is a suspendable function (a coroutine) with
an object oriented context that only exists until the function runs out of
scope. Frames can be used to represent both temporal processes (using the
coroutine) and physical or conceptual objects (using the object oriented
context).

Each FHM program has exactly one root frame. The root frame can recursively
spawn child frames. Each child frame runs in parallel (using cooperative
multitasking) unless it's awaiting another frame or an awaitable event.

Frames can be removed in three ways:

1. The frame's ``remove()`` function is called (either by the frame itself or by
   another frame).
2. The frame's coroutine finishes (i.e. goes out of scope).
3. A parent frame is removed.


Installation
============

*asyncframes* can be installed via `pip`: ::

    pip install asyncframes

*asyncframes* requires an event loop to suspend execution without blocking the
operating system. The default event loop is ``asyncframes.asyncio_eventloop.EventLoop``.
It doesn't depend on any Python packages besides the builtin *asyncio* package.
Some frameworks, like Qt, use their own event loops. When using such frameworks,
the framework's event loop should be reused for *asyncframes* by implementing
the ``asyncframes.AbstractEventLoop`` interface.


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
