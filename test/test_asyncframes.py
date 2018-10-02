# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import datetime
import io
import logging
import math
import threading
import queue
import time
import unittest
from asyncframes import *
from asyncframes import _THREAD_LOCALS

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

        # Register event handler for exceptions raised within passive frames
        def passive_frame_exception_handler(err):
            if isinstance(err, AssertionError):
                raise err # Raise unittest assertions
            self.log.debug("Passive frame exception caught: " + repr(err))
        self.loop.passive_frame_exception_handler = passive_frame_exception_handler

        # Create logger for debugging program flow using time stamped log messages
        # Create time stamped log messages using self.log.debug(...)
        # Test program flow using self.assertLogEqual(...)
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
        loghandler.setFormatter(TimedFormatter("%(message)s"))
        self.log.addHandler(loghandler)

    def assertLogEqual(self, expected):
        expected = '\n'.join(line.strip() for line in expected.strip('\n').split('\n')) # Remove leading and trailing empty lines and white space
        self.assertEqual(expected, self.logstream.getvalue())

    def test_simple(self):
        test = self
        @Frame
        async def main():
            await wait(test, 0.1, '1')
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
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
        test.loop.run(main)
        test.log.debug('done')
        test.assertLogEqual("""
            0.1: done
        """)

    def test_negative_sleep_duration(self):
        test = self
        @MyFrame
        async def main():
            await sleep(-1)
            test.log.debug('done')
        test.loop.run(main)
        test.assertLogEqual("""
            0.0: done
        """)

    def test_await_order_1(self):
        test = self
        @MyFrame
        async def main():
            wait(test, 0.1, '1')
            await wait(test, 0.2, '2')
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
            0.2: 2
        """)

    def test_await_order_2(self):
        test = self
        @MyFrame
        async def main():
            await wait(test, 0.1, '1')
            await wait(test, 0.2, '2')
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
            0.3: 2
        """)

    def test_await_order_3(self):
        test = self
        @MyFrame
        async def main():
            await wait(test, 0.1, '1')
            wait(test, 0.2, '2')
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
        """)

    def test_await_order_4(self):
        test = self
        @MyFrame
        async def main():
            wait(test, 0.1, '1')
            wait(test, 0.2, '2')
        test.loop.run(main)
        test.assertLogEqual("""
        """)

    def test_await_order_5(self):
        test = self
        @MyFrame
        async def main():
            w1 = wait(test, 0.1, '1')
            w2 = wait(test, 0.2, '2')
            await (w1 & w2)
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
            0.2: 2
        """)

    def test_await_order_6(self):
        test = self
        @MyFrame
        async def main():
            w1 = wait(test, 0.1, '1')
            w2 = wait(test, 0.2, '2')
            await (w1 | w2)
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
        """)

    def test_frame_result(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug(await wait(test, 0.1, '1'))
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
            0.1: some result
        """)
    
    def test_blocking_sleep(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug((await sleep(0.1)).args)
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: None
        """)
    
    def test_non_blocking_sleep(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug((await sleep(0)).args)
        test.loop.run(main)
        test.assertLogEqual("""
            0.0: None
        """)

    def test_staticmethod(self):
        test = self
        @MyFrame
        async def main():
            MyFrame.mystaticmethod(test)
        test.loop.run(main)
        test.assertLogEqual("""
            0.0: static method called
        """)

    def test_classvar(self):
        test = self
        @MyFrame
        async def main():
            test.log.debug(MyFrame.classvar)
        test.loop.run(main)
        test.assertLogEqual("""
            0.0: class variable
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
        test.loop.run(f1)

        @MyFrame2
        async def f2():
            with test.assertRaises(InvalidOperationException):
                MyPrimitive()
        test.loop.run(f2)

        @MyFrame
        async def f3():
            f2()
        test.loop.run(f3)

        @MyFrame
        async def f4():
            with test.assertRaises(TypeError):
                MyPrimitive2()
        test.loop.run(f4)

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
        test.loop.run(main)
        test.assertLogEqual("""
            0.0: param=param_value
            0.0: kwparam=kwparam_value
        """)

    def test_Frame_current(self):
        test = self
        test.subframe_counter = 0
        @MyFrame
        async def frame(self):
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
        test.loop.run(frame)
        test.assertEqual(test.subframe_counter, 4)

    def test_remove_self(self):
        test = self
        @Frame
        def frame(self):
            test.log.debug("1")
            self.remove()
            test.log.debug("2") # Frame.remove() doesn't interrupt regular frame functions
        @Frame
        async def async_frame(self):
            test.log.debug("3")
            self.remove()
            test.log.debug("never reached") # Frame.remove() interrupts async frame functions
        test.loop.run(frame)
        test.loop.run(async_frame)
        test.assertLogEqual("""
            0.0: 1
            0.0: 2
            0.0: 3
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
        test.loop.run(main)
        test.log.debug('done')
        test.assertLogEqual("""
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
        test.loop.run(main1)
        @Frame
        async def main2(self):
            w = wait(test, 0.1, '2')
            await (w | w)
        test.loop.run(main2)
        @Frame
        async def main3(self):
            w = sleep(0.1)
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 & a2)
        test.loop.run(main3)
        @Frame
        async def main4(self):
            w = wait(test, 0.1, '3')
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 & a2)
        test.loop.run(main4)
        @Frame
        async def main5(self):
            w = wait(test, 0.1, '4')
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 | a2)
        test.loop.run(main5)
        @Frame
        async def main6(self):
            s = sleep(0.1)
            await (s | s & s)
        test.loop.run(main6)

    def test_finished_before_await(self):
        test = self
        @Frame
        async def main():
            s = sleep(0.1)
            w = wait(test, 0.1, '1')
            test.log.debug((await sleep(0.2)).source)
            test.log.debug((await s).source)
            test.log.debug(await w)
            test.log.debug((await (s | w)).source)
            s_and_w = await (s & w)
            for k in sorted(s_and_w):
                v = s_and_w[k]
                test.log.debug("{}: {}".format(k, v))
            test.log.debug('done')
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
            0.2: sleep(0.2)
            0.2: sleep(0.1)
            0.2: some result
            0.2: sleep(0.1)
            0.2: sleep(0.1): sleep(0.1)
            0.2: wait: some result
            0.2: done
        """)

    def test_custom_event(self):
        test = self
        @Frame
        async def main(self):
            ae = EventSource('my event')

            send_event(0.1, ae)
            send_event(0.2, ae)
            e = await ae
            test.log.debug("'%s' raised '%s' with args '%s'", e.sender, e.source, e.args)
            e = await ae
            test.log.debug("'%s' reraised '%s' with args '%s'", e.sender, e.source, e.args)

            post_event(0.1, ae)
            ae.post(self, 'my event args', 0.2)
            e = await ae
            test.log.debug("'%s' raised '%s' with args '%s'", e.sender, e.source, e.args)
            e = await ae
            test.log.debug("'%s' reraised '%s' with args '%s'", e.sender, e.source, e.args)

            if test.supports_invoke:
                threading.Thread(target=invoke_event, args=(0.1, ae)).start()
                threading.Thread(target=ae.invoke, args=(self, 'my event args', 0.2)).start()
                e = await ae
                test.log.debug("'%s' raised '%s' with args '%s'", e.sender, e.source, e.args)
                e = await ae
                test.log.debug("'%s' reraised '%s' with args '%s'", e.sender, e.source, e.args)
            else:
                await sleep(0.1)
                test.log.debug("'invoke_event' raised 'my event' with args 'my event args'")
                await sleep(0.1)
                test.log.debug("'main' reraised 'my event' with args 'my event args'")
        @Frame
        async def send_event(self, seconds, awaitable_event):
            await sleep(seconds)
            awaitable_event.send(self, 'my event args')
        @Frame
        async def post_event(self, seconds, awaitable_event):
            await sleep(seconds)
            awaitable_event.post(self, 'my event args')
        def invoke_event(seconds, awaitable_event):
            time.sleep(seconds)
            awaitable_event.invoke('invoke_event', 'my event args')

        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 'send_event' raised 'my event' with args 'my event args'
            0.2: 'send_event' reraised 'my event' with args 'my event args'
            0.3: 'post_event' raised 'my event' with args 'my event args'
            0.4: 'main' reraised 'my event' with args 'my event args'
            0.5: 'invoke_event' raised 'my event' with args 'my event args'
            0.6: 'main' reraised 'my event' with args 'my event args'
        """)

    def test_exceptions(self):
        test = self
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
            # It will be caught by EventLoop.passive_frame_exception_handler
            raise_immediately()
            hold() | raise_immediately()
            hold() & raise_immediately()
            await sleep(0.1)
            test.log.debug(3)

            # Raise passive exception woken by event
            # It will be caught by EventLoop.passive_frame_exception_handler
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
        test.loop.run(main)
        test.assertLogEqual("""
            0.0: 1
            0.3: 2
            0.3: Passive frame exception caught: ZeroDivisionError()
            0.3: Passive frame exception caught: ZeroDivisionError()
            0.3: Passive frame exception caught: ZeroDivisionError()
            0.4: 3
            0.5: Passive frame exception caught: ZeroDivisionError()
            0.5: Passive frame exception caught: ZeroDivisionError()
            0.5: Passive frame exception caught: ZeroDivisionError()
        """)

    def test_animate(self):
        test = self
        @Frame
        async def a():
            await animate(0.25, lambda f: test.log.debug(''), 0.1)
        @Frame
        async def main():
            await a()
        test.loop.run(main)
        test.assertLogEqual("""
            0.1
            0.2
            0.2
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
        test.loop.run(frame)

    def test_rerun(self):
        test = self
        @Frame
        async def main():
            await wait(test, 0.1, 'main')
        @Frame
        def raise_exception():
            raise ZeroDivisionError
        test.loop.run(main)
        test.loop.run(main)
        with test.assertRaises(ZeroDivisionError):
            test.loop.run(raise_exception)
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: main
            0.2: main
            0.3: main
        """)

    def test_meta(self):
        test = self
        @Frame
        async def main(self):
            test.assertEqual(str(self), "main")
            test.assertRegex(repr(self), r"<asyncframes.main object at 0x\w*>")
        test.loop.run(main)

    def test_invalid_usage(self):
        test = self
        @Frame
        def raise_already_running():
            test.loop.run(wait, test, 0.0, '')
        with test.assertRaisesRegex(InvalidOperationException, "Another event loop is already running"):
            test.loop.run(raise_already_running)
        with test.assertRaisesRegex(InvalidOperationException, "Can't call frame without a running event loop"):
            wait(test, 0.0, '')

    def test_reawait(self):
        test = self
        @Frame
        async def main():
            s1 = sleep(0.1)
            s2 = sleep(0.2)
            s3 = sleep(0.3)
            test.assertEqual((await (s1 | s2)).source, s1)
            test.log.debug('1')
            test.assertEqual((await (s2 | s3)).source, s2)
            test.log.debug('2')
            test.assertEqual(set([v.source for v in (await (s2 & s3)).values()]), set([s2, s3]))
            test.log.debug('3')
            await s1
            await s2
            await s3
            test.log.debug('4')
        test.loop.run(main)
        test.assertLogEqual("""
            0.1: 1
            0.2: 2
            0.3: 3
            0.3: 4
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

        test.loop.run(main)
        test.assertLogEqual("""
            0.0: case1_1
            0.0: case2_1
            0.0: case3_1
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
        test.loop.run(frame)
        test.assertLogEqual("""
            0.0: 1
            0.1: 2
            0.1: 1
            0.1: 2
        """)

    def test_startup_behaviour(self):
        test=self
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
            self.var = 'value'
            await sleep()
        test.loop.run(frame)

    def test_thread_independance(self):
        test = self
        errors = queue.Queue()
        def test_thread(tc):
            try:
                test.__class__(tc).debug()
            except Exception as err:
                errors.put(err)

        testcases = unittest.defaultTestLoader.getTestCaseNames(test.__class__)
        testcases.remove('test_thread_independance')

        threads = [threading.Thread(target=test_thread, args=(testcase,)) for testcase in testcases]
        for thread in threads: thread.start()
        for thread in threads: thread.join()

        if not errors.empty():
            raise errors.get()

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
            self.loop = EventLoop()
            super().setUp()

    def test_thread_independance(self):
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
                except Exception as err:
                    errors.put(err)

        testcases = unittest.defaultTestLoader.getTestCaseNames(test.__class__)
        testcases.remove('test_thread_independance')

        threads = [TestThread(testcase) for testcase in testcases]
        for thread in threads: thread.start()
        for thread in threads: thread.wait()

        if not errors.empty():
            raise errors.get()

if __name__ == "__main__":
    unittest.main()
