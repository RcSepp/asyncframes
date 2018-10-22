=====================================
asyncframes - Coroutines for everyone
=====================================

.. image:: https://travis-ci.org/RcSepp/asyncframes.svg?branch=master
    :target: https://travis-ci.org/RcSepp/asyncframes

Code repository: https://github.com/RcSepp/asyncframes

Python Package Index: https://pypi.org/project/asyncframes/

----

*asyncframes* is a coroutine library for Python and a reference implementation for the *Frame Hierarchy Programming Model* (FHM). The goal of FHM is to help programmers design clean and maintainable source code. See section `Frame Hierarchy Programming Model`_ for details.
The main features of *asyncframes* are:

- Simple syntax (compared with *asyncio*)
- Hierarchical composition of coroutines
- Creation of coroutine classes (a class whose lifetime is bound to the execution of a coroutine)


Introduction
============

Frame Hierarchy Programming Model
---------------------------------

In the *Frame Hierarchy Programming Model* (FHM) a program is represented as a dynamic tree of *frames*. A frame is a suspendable function (a coroutine) with an object oriented context that only exists until the function runs out of scope. Frames can be used to represent both temporal processes (using the coroutine) and physical or conceptual objects (using the object oriented context).

Each FHM program has exactly one root frame. The root frame can recursively spawn child frames. Each child frame runs in parallel (using cooperative multitasking) unless it's awaiting another frame or an awaitable event.

Frames can be removed in three ways:

1. The frame's ``remove()`` function is called (either by the frame itself or by another frame).
2. The frame's coroutine finishes (i.e. goes out of scope).
3. A parent frame is removed.

Coroutine startup behaviour
---------------------------

There are two opposing strategies to starting coroutines. Immediate strategy (IS), where calling a coroutine directly executes code until the first ``await``, and delayed strategy (DS), where calling a coroutine queues its execution in the event loop. Using IS, coroutines act like single-threaded functions with the ability to suspend execution using ``await``. Using DS, coroutines act like multi-threaded functions, that are scheduled for delayed execution.

In general, IS coroutines are easier to write, for the following reasons:

1. Coroutines without ``await`` behave exactly like normal functions.
2. Initialization code before the first ``await`` is guaranteed to run before execution is returned to the caller.

To emphasize point 2, consider the following example: ::

    from asyncframes import Frame, EventSource, sleep
    from asyncframes.asyncio_eventloop import EventLoop

    @Frame
    async def timer(self, interval):
        # Initialization code
        self.tick = EventSource('timer.tick')

        # Main code
        while True:
            await sleep(1)
            self.tick.post(self)

    @Frame
    async def main_frame():
        tmr = timer(1)
        #await tmr.ready # Uncomment this line to successfully run this example
                         # on asyncframes version 1.2 or above

        for i in range(5):
            await tmr.tick # Using DS, this line will throw "AttributeError:
                           # 'Frame' object has no attribute 'tick'"
            print(i + 1)

    loop = EventLoop()
    loop.run(main_frame)

For these reasons, asyncframes uses IS until version 1.1. Starting version 1.2, asyncframes uses DS by default, with the option to enable IS by passing ``startup_behaviour=FrameStartupBehaviour.immediate``.

Here are the advantages of DS:

1. Most existing coroutine libraries, e.g. asyncio, use DS.
2. Multi-threaded or distributed frames can run entirely on the newly spawned thread or process.

Point 2 refers to frames that run on a separate thread (``PFrame`` s) or on a separate process (``DFrame`` s). To ensure such frames behave according to IS, either the initialization part of the frame has to be executed on the calling frame's thread or the calling frame's thread has to be suspended until the spawned frame is initialized. Both of these methods would defeat the purpose of multi-threading.
To successfully run code like the *timer*-example above on asyncframes version 1.2 or above, we introduced the Frame.ready event source. Frame.ready sends an event as soon as (a) the frame is awaited for the first time or (b) the frame is done (whichever comes first).



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
