Parallel Programming with asyncframes
=====================================

Parallel programming is to write fragments of code that can be executed in parallel. It is used to either speed up code execution or to circumvent blocking operations.

Types of Parallelism
--------------------

There are many types of parallelism. For asyncframes we distinguish the following three types:

1. Cooperative multitasking
2. Shared memory parallelism
3. Distributed memory parallelism

If you understand the differences between these types of parallelism and know about the implications of their implementation in Python, feel free to move on to the next section.

Cooperative multitasking does not actually execute code in parallel. Instead, It allows a program to pause the execution of a function and execute other parts of the program before returning. In Python, such functions can be implemented using generators (functions that use the ``yield`` keyword) or coroutines (functions defined using ``async def``, that can use the ``await`` keyword). We will only focus on coroutines here. By using coroutines on top of an event loop, we can implement a parallel programming environment, where the eventloop acts as the task scheduler and individual coroutines act as tasks that periodically yield execution using the ``await`` keyword. Since this environment never actually switches between CPU threads, it doesn't come with any of the usual caveats of parallel programming, like nondeterministic execution, dead locks and race conditions. However, cooperative multitasking doesn't run faster than serial code and blocking a single coroutine will block the entire program.

Shared memory parallelism is employed when separate execution contexts (i.e. threads) execute code in parallel that accesses a shared pool of memory. In modern computers this is utilized by running separate CPU cores or hardware threads in parallel. In contrast to cooperative multitasking, this type of parallelism does run code in parallel. It therefore requires much more careful code design to avoid dead locks and race conditions, while rewarding the programmer with parallel speedup and non-blocking execution. In Python shared memory parallelism is limited by the Global Interpreter Lock (GIL). The GIL is a mechanism that only allows one thread to interpret Python code at a time. This prohibits parallel speedups, but it doesn't affect the non-blocking behavior of multi-threaded Python code. Since this limitation is not part of the Python standard, it may not apply to all Python distributions and it may even be removed in a future release of CPython. In terms of the Frame Hierarchy Programming Model, we assume that shared memory parallelism *can* result in faster code, and it should be preferred to cooperative multitasking for thread-safe frames.

Distributed memory parallelism is employed when threads cannot access memory of other threads without using specialized memory transfer mechanisms. In modern computers such threads are known as processes. They can either run on the same machine, using memory separated by the operating system, or on physically separate machines. In either case we should assume inter-process communication to be much slower than interactions between shared memory threads. The main advantage of distributed memory parallelism is that it is much more scalable than shared memory parallelism. A modern supercomputer, for example, has thousands of compute nodes with physically separated memory, while the CPUs on each node only employ a small number of hardware threads. In Python multi-processing runs multiple instances of the program. Each process runs a separate Python interpreter, which allows speedup through parallel execution without being affected by the previously mentioned limitations of the GIL. Distributed frames can take advantage of this speedup, as long as they are thread-safe and they don't access global variables of other processes.

.. important:: Distributed frames aren't implemented in asyncframes |version|. This feature is under active development and will be added in a future release.

Parallel Programming using Frames
---------------------------------

The following table summarizes the three types of parallelism of the previous section from a software engineering perspective:

+--------------------------+------------------+--------------+------------+-------------------------+
| | Type of parallelism    | | Implementation | Perks                     | Requirements            |
| |                        | | in asyncframes +--------------+------------+-----------+-------------+
| |                        | |                | | Blocking   | | Parallel | | Thread- | | Localized |
| |                        | |                | | operations | | speedup  | | safety  | | memory    |
+==========================+==================+==============+============+===========+=============+
| Cooperative multitasking | *Frame*          |              |            |           |             |
+--------------------------+------------------+--------------+------------+-----------+-------------+
| Shared memory            | *PFrame* [1]_    | ✓            |            | ✓         |             |
+--------------------------+------------------+--------------+------------+-----------+-------------+
| Distributed memory       | *DFrame* [2]_    | ✓            | ✓          | ✓         | ✓           |
+--------------------------+------------------+--------------+------------+-----------+-------------+

.. [1] *PFrames* require asyncframes v2.0 or above.
.. [2] *DFrames* aren't implemented in asyncframes |version|. This feature is under development and will be added in a future release.

In the Frame Hierarchy Programming Model, parallelism is implemented according to the "concurrency by default" paradigm. By default every frame is maximally parallel (*DFrame*), but the programmer can reduce the degree of parallelism by employing restrictions. *PFrames* are like *DFrames*, but with the restriction of running on the same *process* as their parent frame. *Frames* are like *PFrames*, but with the restriction of running on the same *thread* as their parent frame.

The main advantage of the restriction model is that parallel software can be designed iteratively. The entire program can first be designed using only *Frames* (except blocking operations, which should always be placed inside *PFrames* or *DFrames*; see table). Once completed, the programmer can assure thread-safety of individual frames, promote them to *PFrames* and rerun all unit tests. If the program still produces deterministic correct results (note that multithreading can lead to non-deterministic errors, which only fail with a certain probability!), the programmer can assure individual frames don't access global memory of other processes and further promote them to *DFrames*.

Reasons to choose higher degrees of parallelism
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In general it should be the goal of any frame hierarchy program to promote as many frames as possible to higher degrees of parallelism. Only then can an optimized scheduler efficiently distribute frames across available threads and processes in a transparent and scalable manner. Keep in mind that any *PFrame* *can* be executed on the same thread as it's parent frame if the scheduler decides that this is the most efficient thing to do. For example, if all other available threads are busy. It can even execute different parts of a single frame on different threads. The fewer restrictions are enforced, the more freedom is granted to the scheduler to efficiently parallelize a program.

How to make parts of a program singlethreaded
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are situations where multithreading should be avoided. For example, many user interface libraries, like Qt, are strictly singlethreaded. By only using *Frames* to interact with the user interface, this restriction is satisfied. Programmers can still create *PFrames* or *DFrames* in response to a user interface event, for example to execute a computationally expensive operation in parallel, as long as these parallel frames don't directly access the user interface.

It's important to note that asyncframes doesn't use a master thread. Whenever an eventloop runs a *Frame*, this frame will run on the thread that executed the ``EventLoop.run()`` command. However, this doesn't mean that all *Frames* always run on that same thread. If a *Frame* is created from a *Pframe*, it will run on whatever thread the *Pframe* was running on when it created the *Frame*. This way, a frame hierarchy program can contain multiple serial parts that run on different threads. For example, a program can utilize a singlethreaded user interface library and a singlethreaded database library on different threads. Of course, these concepts also apply to processes if the frame hierarchy contains *DFrames*.

How to disable multithreading entirely
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``EventLoop.run()`` is called, asyncframes allocates multiple threads. The number of allocated threads can be controlled with the ``num_threads`` parameter. By default asyncframes will allocate as many threads as there are available hardware threads on the CPU. To run a program entirely singlethreaded, set the ``num_threads`` parameter to 1. In this scenario, asyncframes will never run any other threads, even if *PFrames* or *DFrames* are used. This is because in the restriction model *PFrames* are free to run on any available thread, but there is only on thread available.

Example
-------

To illustrate the differences between *Frames* and *PFrames*, let's run multiple counters in parallel using blocking operations.

The following frame prints the result of a call to ``printfunc`` three times every 0.3 seconds after an initial delay:

.. literalinclude:: ../../examples/parallel.py
    :lines: 9-14

We also create a parallel frame with the same content:

.. literalinclude:: ../../examples/parallel.py
    :lines: 16-21


The frame ``count_using_frames`` creates three *Frame*-based counters, each starting 0.1 seconds after the previous counter. Again, we also create a *PFrame*-based version, named ``count_using_pframes``:

.. literalinclude:: ../../examples/parallel.py
    :lines: 23-33

Let's see what happens if we run three blocking counters using *Frames*. The first counter prints the character `a`, the second one prints `b` and the third one prints `c`:

>>> loop.run(count_using_frames, printfunc=lambda i: "abc"[i])
aaabbbccc

As we learned in the previous section, *Frames* always run on the same thread as their parent frame. We don't use any *PFrames*, so that thread is the main thread (thread 0). Since we never call ``await`` inside ``frame_counter``, the main thread is blocked until the counter returns, before starting the next counter.

We can visualize which thread each counter runs on, using the ``get_current_eventloop_index()`` function:

>>> loop.run(count_using_frames, printfunc=lambda i: asyncframes.get_current_eventloop_index())
000000000

Now let's repeat the experiment using *PFrames*:

>>> loop.run(count_using_frames, printfunc=lambda i: "abc"[i])
abcabcabc

Each counter still blocks until it is done, but because we now create *PFrame*-based counters, asyncframes can distribute them over individual threads in the thread pool:

>>> loop.run(count_using_frames, printfunc=lambda i: asyncframes.get_current_eventloop_index())
123123123

Note that the used threads are threads 1 through 3. That's because thread 0 is used to run the parent frame (``count_using_pframes``).

Finally, let's restrict the thread pool to three threads:

>>> loop.run(count_using_frames, printfunc=lambda i: "abc"[i], num_threads=3)
abababccc

We notice that the first two counters run in parallel, but the third one is blocked. Let's see which threads were involved in this behavior:

>>> loop.run(count_using_frames, printfunc=lambda i: asyncframes.get_current_eventloop_index(), num_threads=3)
121212111

We use 3 threads. Thread 0 runs the parent frame (``count_using_pframes``), threads 1 runs the `a` counter and thread 2 runs the `b` counter. The `c` counter can't start until a thread becomes available. The first thread to become available is thread 1, after the `a` counter finishes.

.. note:: We used blocking sleep operations here for illustrative purposes only. In production code one should use ``await asyncframes.sleep()`` instead.
