=====================================
asyncframes - Coroutines for everyone
=====================================

.. |rtd_v2| image:: https://img.shields.io/readthedocs/asyncframes/dev.svg?logo=Read%20the%20Docs
    :target: https://asyncframes.readthedocs.io/en/dev/?badge=dev
    :alt: Documentation Status

.. |pypi_v1| image:: https://img.shields.io/badge/pypi-v1.1-blue.svg
    :target: https://pypi.org/project/asyncframes/

.. |github_v1| image:: https://img.shields.io/badge/github-master-brightgreen.svg?style=social&logo=github
    :target: https://github.com/RcSepp/asyncframes/tree/master
.. |github_v2| image:: https://img.shields.io/badge/github-dev-brightgreen.svg?style=social&logo=github
    :target: https://github.com/RcSepp/asyncframes/tree/dev

.. |travis_v1| image:: https://img.shields.io/travis/RcSepp/asyncframes/master.svg?logo=travis
    :target: https://travis-ci.org/RcSepp/asyncframes
.. |travis_v2| image:: https://img.shields.io/travis/RcSepp/asyncframes/dev.svg?logo=travis
    :target: https://travis-ci.org/RcSepp/asyncframes

.. |coverage_v1| image:: https://coveralls.io/repos/github/RcSepp/asyncframes/badge.svg?branch=master
    :target: https://coveralls.io/github/RcSepp/asyncframes?branch=master
.. |coverage_v2| image:: https://coveralls.io/repos/github/RcSepp/asyncframes/badge.svg?branch=dev
    :target: https://coveralls.io/github/RcSepp/asyncframes?branch=dev

.. |license_v1| image:: https://img.shields.io/badge/License-MIT-brightgreen.svg
    :target: https://opensource.org/licenses/MIT
.. |license_v2| image:: https://img.shields.io/badge/License-MIT-brightgreen.svg
    :target: https://opensource.org/licenses/MIT

========= ======================================== ========================================
Version   asyncframes v1                           asyncframes v2                          
========= ======================================== ========================================
Docs                                               |rtd_v2|                                
Download  |pypi_v1|                                *unreleased*                            
Source    |github_v1|                              |github_v2|                             
Status    |travis_v1| |coverage_v1|                |travis_v2| |coverage_v2|               
License   |license_v1|                             |license_v2|                            
========= ======================================== ========================================

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
