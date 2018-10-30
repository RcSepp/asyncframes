# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import datetime
import io
import logging
import math
import threading
import queue
import re
import time
import unittest
import asyncframes
from asyncframes import *
from asyncframes import _THREAD_LOCALS
import line_tracer

# Uncomment the following line to run all tests using PFrames
# Frame = PFrame

# NUM_ITERATIONS controls the number of times each test is executed
NUM_ITERATIONS = 1

# NUM_THREADS controls the number of worker threads to start when running an event loop
# If 0, the number of CPU threads is used (according to os.sched_getaffinity(0))
# If 1, no multithreading will be performed
NUM_THREADS = 0

# If true, any exceptions during an iteration of a test case will print a full line-by-line trace of the executed test
USE_TRACER = False
TRACE_OUTPUT = "./trace.txt" # Output file for trace output or None to print to standard output
TRACE_MODE = line_tracer.Trace.Mode.on_error


class nullcontext(object):
    """A context manager that does nothing.
    
    See https://docs.python.org/3/library/contextlib.html#contextlib.nullcontext
    Implemented here for Python versions before 3.7
    """
    def __init__(self, enter_result=None):
        self.enter_result = enter_result
    def __enter__(self):
        return self.enter_result
    def __exit__(self, exc_type, exc_value, traceback):
        return

class MyFrame(Frame):
    @staticmethod
    def mystaticmethod(test):
        test.log.debug('static method called')
    classvar = 'class variable'

@MyFrame
async def wait(test, seconds, name):
    result = await sleep(seconds)
    test.log.debug(name)
    return "some result"

EVENTLOOP_CLASS = None
SKIP_TEST_CASE = None

class TestAsyncFrames(unittest.TestCase):
    def setUp(self):
        # Create default event loop if no event loop was created by a base class
        if not hasattr(self, 'loop'):
            from asyncframes.asyncio_eventloop import EventLoop
            self.loop = EventLoop()

        # Announce event loop if different
        global EVENTLOOP_CLASS
        if self.loop.__class__ != EVENTLOOP_CLASS:
            print()
            print("Using {}.{}".format(self.loop.__class__.__module__, self.loop.__class__.__name__))
            EVENTLOOP_CLASS = self.loop.__class__
        
        # Check if the event loop class implements AbstractEventLoop._invoke
        self.supports_invoke = self.loop.__class__._invoke != AbstractEventLoop._invoke

        # Register event handler for exceptions raised within frames
        def frame_exception_handler(err):
            if isinstance(err, AssertionError):
                return False # Raise unittest assertions
            self.log.debug("Frame exception caught: " + repr(err))
            return True
        self.loop.frame_exception_handler = frame_exception_handler

        # Create logger for debugging program flow using time stamped log messages
        # Create time stamped log messages using self.log.debug(...)
        # Test program flow by passing an expected_log to self.run_frame()
        self.log = logging.getLogger(self._testMethodName + str(threading.get_ident()))
        self.log.setLevel(logging.DEBUG)
        self.logstream = io.StringIO()
        loghandler = logging.StreamHandler(self.logstream)
        loghandler.setLevel(logging.DEBUG)
        class TimedFormatter(logging.Formatter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.starttime = datetime.datetime.now()
            def format(self, record):
                t = (datetime.datetime.now() - self.starttime).total_seconds()
                msg = super().format(record)
                return str(math.floor(t * 10) / 10) + ": " + msg if msg else str(math.floor(t * 10) / 10)
        self.logformatter = TimedFormatter("%(message)s")
        loghandler.setFormatter(self.logformatter)
        self.log.addHandler(loghandler)

    def run_frame(self, frame, *frameargs, expected_log=None, assert_raises=None, assert_raises_regex=None):
        @Frame
        async def mainframe():
            self.logstream.truncate(0) # Reset log
            self.logstream.seek(0) # Reset log
            self.logformatter.starttime = datetime.datetime.now() # Reset log start time
            await frame(*frameargs)
        cm = line_tracer.Trace(line_tracer.Trace.Mode.on_error, TRACE_OUTPUT, True) if USE_TRACER else nullcontext()
        for _ in range(NUM_ITERATIONS):
            with cm:
                try:
                    self.loop.run(mainframe, num_threads=NUM_THREADS)
                    self.log.debug('done')
                    if expected_log is not None:
                        # Compare log with expected_log
                        expected = '\n'.join(line.strip() for line in expected_log.strip('\n').split('\n')) # Remove leading and trailing empty lines and white space
                        self.assertEqual(expected, self.logstream.getvalue())
                except Exception as err:
                    if assert_raises:
                        failed = type(err) != assert_raises
                    elif assert_raises_regex:
                        failed = type(err) != assert_raises_regex[0] or not re.match(assert_raises_regex[1], str(err))
                    else:
                        failed = True
                    if failed:
                        raise
                else:
                    if assert_raises or assert_raises_regex:
                        raise AssertionError((assert_raises or assert_raises_regex).__name__ + " not raised")

    def test_simple(self):
        test = self
        @Frame
        async def main():
            await wait(test, 0.1, '1')
        test.run_frame(main, expected_log="""
            0.1: 1
            0.1: done
        """)

    def test_regular_function_mainframe(self):
        test = self
        @Frame
        async def remove_after(frame, seconds):
            await sleep(seconds)
            frame.remove()
        @Frame
        def main(self):
            remove_after(self, 0.1)
        test.run_frame(main, expected_log="""
            0.1: done
        """)

    def test_negative_sleep_duration(self):
        test = self
        @MyFrame
        async def main():
            await sleep(-1)
        test.run_frame(main, expected_log="""
            0.0: done
        """)

    def test_await_order_1(self):
        test = self
        @MyFrame
        async def main():
            wait(test, 0.1, '1')
            await wait(test, 0.2, '2')
        test.run_frame(main, expected_log="""
            0.1: 1
            0.2: 2
            0.2: done
        """)

    def test_await_order_2(self):
        test = self
        @MyFrame
        async def main():
            await wait(test, 0.1, '1')
            await wait(test, 0.2, '2')
        test.run_frame(main, expected_log="""
            0.1: 1
            0.3: 2
            0.3: done
        """)

    def test_await_order_3(self):
        test = self
        @MyFrame
        async def main():
            await wait(test, 0.1, '1')
            wait(test, 0.2, '2')
        test.run_frame(main, expected_log="""
            0.1: 1
            0.1: done
        """)

    def test_await_order_4(self):
        test = self
        @MyFrame
        async def main():
            wait(test, 0.1, '1')
            wait(test, 0.2, '2')
        test.run_frame(main, expected_log="""
            0.0: done
        """)

    def test_await_order_5(self):
        test = self
        @MyFrame
        async def main():
            w1 = wait(test, 0.1, '1')
            w2 = wait(test, 0.2, '2')
            await (w1 & w2)
        test.run_frame(main, expected_log="""
            0.1: 1
            0.2: 2
            0.2: done
        """)

    def test_await_order_6(self):
        test = self
        @MyFrame
        async def main():
            w1 = wait(test, 0.1, '1')
            w2 = wait(test, 0.2, '2')
            await (w1 | w2)
        test.run_frame(main, expected_log="""
            0.1: 1
            0.1: done
        """)

    def test_frame_result(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug(await wait(test, 0.1, '1'))
        test.run_frame(main, expected_log="""
            0.1: 1
            0.1: some result
            0.1: done
        """)
    
    def test_blocking_sleep(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug(await sleep(0.1))
        test.run_frame(main, expected_log="""
            0.1: None
            0.1: done
        """)
    
    def test_non_blocking_sleep(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug(await sleep(0))
        test.run_frame(main, expected_log="""
            0.0: None
            0.0: done
        """)

    def test_staticmethod(self):
        test = self
        @MyFrame
        async def main():
            MyFrame.mystaticmethod(test)
        test.run_frame(main, expected_log="""
            0.0: static method called
            0.0: done
        """)

    def test_classvar(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug(MyFrame.classvar)
        test.run_frame(main, expected_log="""
            0.0: class variable
            0.0: done
        """)

    def test_primitive(self):
        test = self
        class MyPrimitive(Primitive):
            def __init__(self):
                super().__init__(MyFrame)
        class MyPrimitive2(Primitive):
            def __init__(self):
                super().__init__(MyPrimitive)
        class MyFrame2(Frame):
            pass

        @MyFrame
        async def f1():
            MyPrimitive()
        test.run_frame(f1)

        @MyFrame2
        async def f2():
            MyPrimitive()
        test.run_frame(f2, assert_raises=InvalidOperationException)

        @MyFrame
        async def f3():
            await f2()
        test.run_frame(f3)

        @MyFrame
        async def f4():
            with test.assertRaises(TypeError):
                MyPrimitive2()
        test.run_frame(f4)

        with test.assertRaises(InvalidOperationException):
            MyPrimitive()

    def test_frameclassargs(self):
        test = self
        class MyFrame2(Frame):
            def __init__(self, param, kwparam):
                super().__init__()
                test.log.debug("param=%s" % param)
                test.log.debug("kwparam=%s" % kwparam)
        @MyFrame2('param_value', kwparam='kwparam_value')
        async def main():
            pass
        test.run_frame(main, expected_log="""
            0.0: param=param_value
            0.0: kwparam=kwparam_value
            0.0: done
        """)

    def test_Frame_current(self):
        test = self
        @MyFrame
        async def frame(self):
            test.subframe_counter = 0
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
            async_subframe() # Test passive async frame
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
            await async_subframe() # Test active async frame
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
            subframe() # Test passive frame
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
            @Frame
            async def remove_after(frame, seconds):
                await sleep(seconds)
                frame.remove()
            sf = subframe()
            remove_after(sf, 0.1)
            await sf # Test active frame
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
        @MyFrame
        async def async_subframe(self):
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
            await sleep()
            test.subframe_counter += 1
        @MyFrame
        def subframe(self):
            test.assertEqual(_THREAD_LOCALS._current_frame, self)
            test.subframe_counter += 1
        test.run_frame(frame)
        test.assertEqual(test.subframe_counter, 4)

    def test_remove_self(self):
        test = self
        # @Frame
        # def frame(self):
        #     test.log.debug("1")
        #     self.remove()
        #     test.log.debug("2") # Frame.remove() doesn't interrupt regular frame functions
        # test.run_frame(frame, expected_log="""
        #     0.0: 1
        #     0.0: 2
        #     0.0: done
        # """)
        @Frame
        async def async_frame(self):
            test.log.debug("3")
            self.remove()
            test.log.debug("never reached") # Frame.remove() interrupts async frame functions
        test.run_frame(async_frame, expected_log="""
            0.0: 3
            0.0: done
        """)

    def test_reremove(self):
        test = self
        class MyPrimitive(Primitive):
            def __init__(self):
                super().__init__(Frame)
        @Frame
        async def remove_after(frame, seconds):
            await sleep(seconds)
            test.log.debug('Removing frame')
            frame.remove()
        @Frame
        async def main(self):
            self.p = None
            @Frame
            async def primitive_owner():
                self.p = MyPrimitive()
                await sleep(0.0)
                test.log.debug('Removing primitive')
            primitive_owner()

            remove_after(self, 0.3)
            a = (self.free | sleep(0.1))
            await a
            test.log.debug('Re-removing any_')
            test.assertEqual(a.remove(), False)

            s = sleep(0.1)
            a = (self.free & s)
            await a
            test.log.debug('Re-removing all_')
            test.assertEqual(a.remove(), False)

            test.log.debug('Re-removing event source')
            test.assertEqual(s.remove(), False)

            test.log.debug('Re-removing primitive')
            test.assertEqual(self.p.remove(), False)

            test.log.debug('Re-removing frame')
            test.assertEqual(self.remove(), False)
        test.run_frame(main, expected_log="""
            0.0: Removing primitive
            0.1: Re-removing any_
            0.3: Removing frame
            0.3: Re-removing all_
            0.3: Re-removing event source
            0.3: Re-removing primitive
            0.3: Re-removing frame
            0.3: done
        """)

    def test_awaited_by_multiple(self):
        test = self
        @Frame
        async def waitfor(w):
            await w
        @Frame
        async def main1(self):
            w = wait(test, 0.1, '1')
            await (w & w)
        test.run_frame(main1)
        @Frame
        async def main2(self):
            w = wait(test, 0.1, '2')
            await (w | w)
        test.run_frame(main2)
        @Frame
        async def main3(self):
            w = sleep(0.1)
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 & a2)
        test.run_frame(main3)
        @Frame
        async def main4(self):
            w = wait(test, 0.1, '3')
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 & a2)
        test.run_frame(main4)
        @Frame
        async def main5(self):
            w = wait(test, 0.1, '4')
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 | a2)
        test.run_frame(main5)
        @Frame
        async def main6(self):
            s = sleep(0.1)
            await (s | s & s)
        test.run_frame(main6)

    def test_finished_before_await(self):
        test = self
        @Frame
        async def main():
            s = sleep(0.1)
            w = wait(test, 0.1, '1')
            await sleep(0.2)
            await s
            test.log.debug(await w)
            awaitable_repr = Awaitable.__repr__
            Awaitable.__repr__ = Awaitable.__str__
            test.log.debug(await (s | w))
            test.log.debug(await (s & w))
            Awaitable.__repr__ = awaitable_repr
        test.run_frame(main, expected_log="""
            0.1: 1
            0.2: some result
            0.2: (sleep(0.1), None)
            0.2: [None, 'some result']
            0.2: done
        """)

    def test_custom_event(self):
        test = self
        @Frame
        async def main(self):
            ae = Event('my event')

            send_event(0.1, ae)
            send_event(0.2, ae)
            sender, args = await ae
            test.log.debug("'%s' raised '%s' with args '%s'", sender, ae, args)
            sender, args = await ae
            test.log.debug("'%s' reraised '%s' with args '%s'", sender, ae, args)

            post_event(0.1, ae)
            ae.post((self, 'my event args'), 0.2)
            sender, args = await ae
            test.log.debug("'%s' raised '%s' with args '%s'", sender, ae, args)
            sender, args = await ae
            test.log.debug("'%s' reraised '%s' with args '%s'", sender, ae, args)

            if test.supports_invoke:
                threading.Thread(target=invoke_event, args=(0.1, ae)).start()
                threading.Thread(target=ae.post, args=((self, 'my event args'), 0.2)).start()
                sender, args = await ae
                test.log.debug("'%s' raised '%s' with args '%s'", sender, ae, args)
                sender, args = await ae
                test.log.debug("'%s' reraised '%s' with args '%s'", sender, ae, args)
            else:
                await sleep(0.1)
                test.log.debug("'invoke_event' raised 'my event' with args 'my event args'")
                await sleep(0.1)
                test.log.debug("'main' reraised 'my event' with args 'my event args'")
        @Frame
        async def send_event(self, seconds, awaitable_event):
            await sleep(seconds)
            awaitable_event.send((self, 'my event args'))
        @Frame
        async def post_event(self, seconds, awaitable_event):
            await sleep(seconds)
            awaitable_event.post((self, 'my event args'))
        def invoke_event(seconds, awaitable_event):
            time.sleep(seconds)
            awaitable_event.post(('invoke_event', 'my event args'))

        test.run_frame(main, expected_log="""
            0.1: 'send_event' raised 'my event' with args 'my event args'
            0.2: 'send_event' reraised 'my event' with args 'my event args'
            0.3: 'post_event' raised 'my event' with args 'my event args'
            0.4: 'main' reraised 'my event' with args 'my event args'
            0.5: 'invoke_event' raised 'my event' with args 'my event args'
            0.6: 'main' reraised 'my event' with args 'my event args'
            0.6: done
        """)

    def test_exceptions(self):
        test = self
        test.maxDiff = None
        @Frame
        async def main():
            # Catch exception raised from active frame
            with test.assertRaises(ZeroDivisionError):
                await raise_immediately()
            with test.assertRaises(ZeroDivisionError):
                await (hold() | raise_immediately())
            with test.assertRaises(ZeroDivisionError):
                await (hold() & raise_immediately())
            test.log.debug(1)

            # Catch exception raised from active frame woken by event
            with test.assertRaises(ZeroDivisionError):
                await raise_delayed()
            with test.assertRaises(ZeroDivisionError):
                await (hold() | raise_delayed())
            with test.assertRaises(ZeroDivisionError):
                await (hold() & raise_delayed())
            test.log.debug(2)

            # Raise passive exception
            # It will be caught by EventLoop.frame_exception_handler
            raise_immediately()
            hold() | raise_immediately()
            hold() & raise_immediately()
            await sleep(0.1)
            test.log.debug(3)

            # Raise passive exception woken by event
            # It will be caught by EventLoop.frame_exception_handler
            raise_delayed()
            hold() | raise_delayed()
            hold() & raise_delayed()
            await sleep(0.2)
        @Frame
        async def raise_immediately():
            raise ZeroDivisionError()
        @Frame
        async def raise_delayed():
            await sleep(0.1)
            raise ZeroDivisionError()
        test.run_frame(main, expected_log="""
            0.0: Frame exception caught: ZeroDivisionError()
            0.0: Frame exception caught: ZeroDivisionError()
            0.0: Frame exception caught: ZeroDivisionError()
            0.0: 1
            0.1: Frame exception caught: ZeroDivisionError()
            0.2: Frame exception caught: ZeroDivisionError()
            0.3: Frame exception caught: ZeroDivisionError()
            0.3: 2
            0.3: Frame exception caught: ZeroDivisionError()
            0.3: Frame exception caught: ZeroDivisionError()
            0.3: Frame exception caught: ZeroDivisionError()
            0.4: 3
            0.5: Frame exception caught: ZeroDivisionError()
            0.5: Frame exception caught: ZeroDivisionError()
            0.5: Frame exception caught: ZeroDivisionError()
            0.6: done
        """)

    def test_animate(self):
        test = self
        @Frame
        async def a():
            await animate(0.25, lambda f: test.log.debug(''), 0.1)
        @Frame
        async def main():
            await a()
        test.run_frame(main, expected_log="""
            0.1
            0.2
            0.2
            0.2: done
        """)

    def test_unfinished_await(self):
        test = self
        @MyFrame
        async def frame():
            await subframe()
            await (subframe() | hold())
            await (subframe() & sleep())
        @MyFrame
        async def subframe():
            await sleep()
            await sleep()
        test.run_frame(frame)

    def test_rerun(self):
        test = self
        @Frame
        async def main():
            await wait(test, 0.1, 'main')
        @Frame
        def raise_exception():
            raise ZeroDivisionError
        test.run_frame(main, expected_log="""
            0.1: main
            0.1: done
        """)
        test.run_frame(main, expected_log="""
            0.1: main
            0.1: done
        """)
        test.run_frame(raise_exception, assert_raises=ZeroDivisionError)
        test.run_frame(main, expected_log="""
            0.1: main
            0.1: done
        """)

    def test_meta(self):
        test = self
        @Frame
        async def main(self):
            test.assertEqual(str(self), "main")
            test.assertRegex(repr(self), r"<asyncframes.main object at 0x\w*>")
        test.run_frame(main)

    def test_invalid_usage(self):
        test = self
        @Frame
        def raise_already_running():
            test.loop.run(wait, test, 0.0, '', num_threads=NUM_THREADS)
        test.run_frame(raise_already_running, assert_raises_regex=(InvalidOperationException, "Another event loop is already running"))
        with test.assertRaisesRegex(InvalidOperationException, "Can't call frame without a running event loop"):
            wait(test, 0.0, '')

    def test_reawait(self):
        test = self
        @Frame
        async def main():
            s1 = sleep(0.1)
            s2 = sleep(0.2)
            s3 = sleep(0.3)
            test.assertEqual((await (s1 | s2))[0], s1)
            test.log.debug('1')
            test.assertEqual((await (s2 | s3))[0], s2)
            test.log.debug('2')
            test.assertEqual(await (s2 & s3), [None, None])
            test.log.debug('3')
            await s1
            await s2
            await s3
            test.log.debug('4')
        test.run_frame(main, expected_log="""
            0.1: 1
            0.2: 2
            0.3: 3
            0.3: 4
            0.3: done
        """)

    def test_ready(self):
        test = self
        @Frame
        async def case1():
            test.log.debug('case1_1')
        @Frame
        async def case2():
            test.log.debug('case2_1')
            await hold()
            test.log.debug('case2_2')
        @Frame
        async def case3():
            test.log.debug('case3_1')
            raise ZeroDivisionError()
        @Frame
        async def main():
            await case1().ready
            await case2().ready
            c3 = case3()
            with test.assertRaises(ZeroDivisionError):
                await (c3.ready | c3)
            test.assertFalse(c3.ready)

        test.run_frame(main, expected_log="""
            0.0: case1_1
            0.0: case2_1
            0.0: case3_1
            0.0: Frame exception caught: ZeroDivisionError()
            0.0: done
        """)

    def test_recursive_ready(self):
        test = self
        @Frame
        async def frame1():
            @Frame
            async def frame2():
                @Frame
                async def frame3():
                    @Frame
                    async def frame4():
                        test.log.debug('frame4 ready')
                        await sleep()
                    test.log.debug('frame3 ready')
                    await frame4()
                test.log.debug('frame2 ready')
                await frame3()
            test.log.debug('frame1 ready')
            await frame2()
        @Frame
        async def main(self):
            await frame1().ready
        test.run_frame(main, expected_log="""
            0.0: frame1 ready
            0.0: frame2 ready
            0.0: frame3 ready
            0.0: frame4 ready
            0.0: done
        """)

    def test_free(self):
        test = self
        @Frame
        async def frame():
            sf = subframe()
            await sleep(0.1)
            sf.remove()

            sf = subframe()
            await sf.ready
        @Frame
        async def subframe(self):
            test.log.debug('1')
            await self.free
            test.log.debug('2')
        test.run_frame(frame, expected_log="""
            0.0: 1
            0.1: 2
            0.1: 1
            0.1: 2
            0.1: done
        """)

    def test_delayed_await(self):
        test = self
        @Frame
        async def main():
            f = raise_exception()
            await sleep(0.1)
            with test.assertRaises(ZeroDivisionError):
                await f
            test.log.debug('after exception')
        @Frame
        async def raise_exception():
            raise ZeroDivisionError
        test.run_frame(main, expected_log="""
            0.0: Frame exception caught: ZeroDivisionError()
            0.1: after exception
            0.1: done
        """)

        test = self
        @Frame
        async def main():
            f = raise_exception()
            await sleep(0.1)
            await f
            test.log.debug('after exception')
        @Frame
        async def raise_exception():
            raise ZeroDivisionError
        test.run_frame(main, assert_raises=ZeroDivisionError)

    def test_startup_behaviour(self):
        test = self
        @Frame
        async def frame():
            sf = immediate_subframe()
            test.assertEqual(sf.var, 'value')
            await sf.ready
            test.assertEqual(sf.var, 'value')

            sf = delayed_subframe()
            with test.assertRaises(AttributeError):
                test.assertEqual(sf.var, 'value')
            await sf.ready
            test.assertEqual(sf.var, 'value')
        @Frame(startup_behaviour=FrameStartupBehaviour.immediate)
        async def immediate_subframe(self):
            self.var = 'value'
        @Frame(startup_behaviour=FrameStartupBehaviour.delayed)
        async def delayed_subframe(self):
            time.sleep(0.1)
            self.var = 'value'
            await sleep()
        test.run_frame(frame)

    def test_pframe(self):
        test = self
        @PFrame
        async def pframe():
            pframe_threadid = threading.get_ident()
            test.log.debug('pframe_1')
            await sleep(0.1)
            test.log.debug('pframe_2')
            await sleep(0.1)
            test.log.debug('pframe_3')
        @asyncframes.Frame # This has to be a Frame to test successfully. Make sure it's a Frame even when 'Frame' is overwritten with 'PFrame'
        async def main():
            main_threadid = threading.get_ident()
            p = pframe()
            await p.ready
            test.assertEqual(threading.get_ident(), main_threadid)
            test.log.debug('main_1')
            await p
            test.assertEqual(threading.get_ident(), main_threadid)
            test.log.debug('main_2')
        test.run_frame(main, expected_log="""
            0.0: pframe_1
            0.0: main_1
            0.1: pframe_2
            0.2: pframe_3
            0.2: main_2
            0.2: done
        """)

    def test_pframe_send(self):
        test = self
        @PFrame
        async def pframe(e):
            await e
        @PFrame
        async def pframe2(self):
            self.e = Event('my_event')
            await self.e
        @Frame
        async def main():
            e = Event('my_event')
            p = pframe(e)
            await p.ready
            e.send()
            test.assertEqual(p.removed, True)

            p2 = pframe2()
            await p2.ready
            p2.e.send()
            test.assertEqual(p2.removed, True)
        test.run_frame(main)

    @unittest.skip('Not yet working')
    def test_send_across_threads(self):
        test = self
        @Frame(thread_idx=2)
        async def frame1(e):
            print("frame1 (eventloop {}) awaits e".format(get_current_eventloop_index()))
            await e
            print("frame1 (eventloop {}) woke up".format(get_current_eventloop_index()))
            test.log.debug('1')
        @Frame(thread_idx=3)
        async def frame2(e):
            print("frame2 (eventloop {}) wakes up e".format(get_current_eventloop_index()))
            e.send()
            print("frame2 (eventloop {}) continues".format(get_current_eventloop_index()))
            test.log.debug('2')
        @Frame
        async def main(self):
            print('----------')
            e = Event('my_event')
            f1 = frame1(e)
            await f1.ready
            f2 = frame2(e)
            await f1
        test.run_frame(main, expected_log="""
            0.0: 1
            0.0: 2
            0.0: done
        """)

    @unittest.skip('Not yet working')
    def test_ready_across_threads(self):
        test = self
        @Frame(thread_idx=2)
        async def frame1():
            time.sleep(0.1)
            test.log.debug('2')
            print(2)
            await sleep()
            test.log.debug('4')
            print(4)
        @Frame(thread_idx=3)
        async def frame2(f1):
            test.log.debug('1')
            print(1)
            await f1.ready
            time.sleep(0.1)
            test.log.debug('3')
            print(3)
        @Frame
        async def main(self):
            print('----------')
            f1 = frame1()
            await frame2(f1)
        test.run_frame(main, expected_log="""
            0.0: 1
            0.1: 2
            0.2: 3
            0.2: 4
            0.2: done
        """)

    @unittest.skip('Not yet working')
    def test_free_across_threads(self):
        """Test awaiting the free event from a thread different than the one
        from the removed frame.

        Test status:
        Deterministic

        Expected behaviour:
        When frame f1 is to be removed, all code between `await f1.free` and the
        next await or the end of the frame should be executed before f1 is
        actually removed. This behaviour allows cleanup code to run before the
        frame is removed.

        Faced issue:
        Send is expected to only return once the event has been handled. This
        does not apply when sending across threads. If the awaiting frame runs
        on another thread than the sending frame, send() behaves like post(). It
        would violate the thread-restriction to directly execute the awaiting
        frame. Instead, it posts the request into the awaiting thread's
        eventloop and returns before the posted request is handled.
        """

        test = self
        @Frame(thread_idx=2)
        async def frame1():
            await sleep(0.1)
            test.log.debug('2')
            print(2)
        @Frame(thread_idx=3)
        async def frame2(f1):
            test.log.debug('1')
            print(1)
            await f1.free
            time.sleep(0.1)
            test.log.debug('3 ' + str(f1.removed))
            print(3, f1.removed)
        @Frame
        async def main(self):
            print('----------')
            f1 = frame1()
            await frame2(f1)
        test.run_frame(main, expected_log="""
            0.0: 1
            0.1: 2
            0.2: 3 False
            0.2: done
        """)

    @unittest.skip('Not yet working')
    def test_delayed_await_free(self):
        """Test removing a frame before the free event is being awaited.

        Expected behaviour:
        If a frame is removed, removal is suspended until any frames awaiting
        the free event of the removed frame await another awaitable or finish.
        If any awaitables, besides auto-resetting events, are awaited after the
        event was emitted, they wake up immediately. Accordingly, awaiting free
        should suspend frame removal, even if free is only awaited after the
        removal was issued. This behaviour assures that cleanup code is always
        executed before frame removal, even if the frame was busy while frame
        removal was initiated.
        """

        test = self
        @Frame(thread_idx=2)
        async def frame1(self):
            await sleep(0.1)
            test.log.debug('2')
            print(2)
            await self.free
            test.log.debug('3')
            print(3)
        @Frame(thread_idx=3)
        async def frame2(f1):
            test.log.debug('1')
            print(1)
            f1.remove()
            test.log.debug('4 ' + str(f1.removed))
            print(4, f1.removed)
        @Frame
        async def main(self):
            print('----------')
            f1 = frame1()
            await frame2(f1)
        test.run_frame(main, expected_log="""
            0.0: 1
            0.1: 2
            0.2: 3 False
            0.2: done
        """)

    def test_thread_independence(self):
        test = self
        errors = queue.Queue()
        def test_thread(tc):
            try:
                test.__class__(tc).debug()
            except unittest.SkipTest:
                pass
            except Exception as err:
                errors.put(err)

        testcases = unittest.defaultTestLoader.getTestCaseNames(test.__class__)
        testcases.remove('test_thread_independence')

        threads = [threading.Thread(target=test_thread, args=(testcase,)) for testcase in testcases]
        for thread in threads:
            thread.daemon = True
            thread.start()
            time.sleep(0.1) # Delay test starts to reduce the effect of startup latency on code timings
        endtime = datetime.datetime.now() + datetime.timedelta(seconds=5) # Limit processing time to 5 seconds
        for thread in threads: thread.join(max(0, (endtime - datetime.datetime.now()).total_seconds()))

        for i, thread in enumerate(threads):
            if thread.is_alive():
                print(testcases[i] + " did not finish")

        if not errors.empty():
            raise Exception(str(errors.qsize()) + " test cases failed") from errors.get()

class TestPyQt5EventLoop(TestAsyncFrames):
    def setUp(self):
        # Create PyQt5 event loop
        try:
            from asyncframes.pyqt5_eventloop import EventLoop
        except ImportError:
            # Announce that we skip this test case, if not announced before
            global SKIP_TEST_CASE
            if self.__class__ != SKIP_TEST_CASE:
                print()
                print("Unable to import asyncframes.pyqt5_eventloop. Skipping unit tests for this event loop.")
                SKIP_TEST_CASE = self.__class__

            raise unittest.SkipTest
        else:
            self.loop = EventLoop(gui_enabled=False)
            super().setUp()

    def test_thread_independence(self):
        test = self
        errors = queue.Queue()
        import PyQt5.Qt
        class TestThread(PyQt5.Qt.QThread):
            err = None
            def __init__(self, tc):
                super().__init__()
                self.tc = tc
            def run(self):
                try:
                    test.__class__(self.tc).debug()
                except unittest.SkipTest:
                    pass
                except Exception as err:
                    errors.put(err)

        testcases = unittest.defaultTestLoader.getTestCaseNames(test.__class__)
        testcases.remove('test_thread_independence')

        threads = [TestThread(testcase) for testcase in testcases]
        for thread in threads:
            thread.start()
            time.sleep(0.1) # Delay test starts to reduce the effect of startup latency on code timings
        for thread in threads: thread.wait()

        if not errors.empty():
            raise Exception(str(errors.qsize()) + " test cases failed") from errors.get()

if __name__ == "__main__":
    unittest.main()
