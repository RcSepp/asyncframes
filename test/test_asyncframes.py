# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import datetime
import io
import logging
import math
import threading
import time
import unittest
from asyncframes import sleep, hold, animate, InvalidOperationException, EventSource, Frame, Primitive, AbstractEventLoop

class MyFrame(Frame):
    @staticmethod
    def mystaticmethod():
        log.debug('static method called')
    classvar = 'class variable'

@MyFrame
async def wait(seconds, name):
    result = await sleep(seconds)
    log.debug(name)
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
            log.debug("Passive frame exception caught: " + repr(err))
        self.loop.passive_frame_exception_handler = passive_frame_exception_handler

        # Create logger for debugging program flow using time stamped log messages
        # Create time stamped log messages using log.debug(...)
        # Test program flow using self.assertLogEqual(...)
        global log
        log = logging.getLogger(__name__)
        log.setLevel(logging.DEBUG)
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
        log.addHandler(loghandler)

    def assertLogEqual(self, expected):
        expected = '\n'.join(line.strip() for line in expected.strip('\n').split('\n')) # Remove leading and trailing empty lines and white space
        self.assertEqual(expected, self.logstream.getvalue())

    def test_simple(self):
        @Frame
        async def main():
            await wait(0.1, '1')
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
        """)

    def test_regular_function_mainframe(self):
        @Frame
        async def remove_after(frame, seconds):
            await sleep(seconds)
            frame.remove()
        @Frame
        def main(self):
            remove_after(self, 0.1)
        self.loop.run(main)
        log.debug('done')
        self.assertLogEqual("""
            0.1: done
        """)

    def test_negative_sleep_duration(self):
        @MyFrame
        async def main():
            await sleep(-1)
            log.debug('done')
        self.loop.run(main)
        self.assertLogEqual("""
            0.0: done
        """)

    def test_await_order_1(self):
        @MyFrame
        async def main():
            wait(0.1, '1')
            await wait(0.2, '2')
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
            0.2: 2
        """)

    def test_await_order_2(self):
        @MyFrame
        async def main():
            await wait(0.1, '1')
            await wait(0.2, '2')
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
            0.3: 2
        """)

    def test_await_order_3(self):
        @MyFrame
        async def main():
            await wait(0.1, '1')
            wait(0.2, '2')
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
        """)

    def test_await_order_4(self):
        @MyFrame
        async def main():
            wait(0.1, '1')
            wait(0.2, '2')
        self.loop.run(main)
        self.assertLogEqual("""
        """)

    def test_await_order_5(self):
        @MyFrame
        async def main():
            w1 = wait(0.1, '1')
            w2 = wait(0.2, '2')
            await (w1 & w2)
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
            0.2: 2
        """)

    def test_await_order_6(self):
        @MyFrame
        async def main():
            w1 = wait(0.1, '1')
            w2 = wait(0.2, '2')
            await (w1 | w2)
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
        """)

    def test_frame_result(self):
        @MyFrame
        async def main():
            log.debug(await wait(0.1, '1'))
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
            0.1: some result
        """)
    
    def test_blocking_sleep(self):
        @MyFrame
        async def main():
            log.debug((await sleep(0.1)).args)
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: None
        """)
    
    def test_non_blocking_sleep(self):
        @MyFrame
        async def main():
            log.debug((await sleep(0)).args)
        self.loop.run(main)
        self.assertLogEqual("""
            0.0: None
        """)

    def test_staticmethod(self):
        @MyFrame
        async def main():
            MyFrame.mystaticmethod()
        self.loop.run(main)
        self.assertLogEqual("""
            0.0: static method called
        """)

    def test_classvar(self):
        @MyFrame
        async def main():
            log.debug(MyFrame.classvar)
        self.loop.run(main)
        self.assertLogEqual("""
            0.0: class variable
        """)

    def test_primitive(self):
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
        self.loop.run(f1)

        @MyFrame2
        async def f2():
            MyPrimitive()
        with self.assertRaises(InvalidOperationException):
            self.loop.run(f2)

        @MyFrame
        async def f3():
            f2()
        self.loop.run(f3)

        @MyFrame
        async def f4():
            MyPrimitive2()
        with self.assertRaises(TypeError):
            self.loop.run(f4)

        with self.assertRaises(InvalidOperationException):
            MyPrimitive()

    def test_frameclassargs(self):
        class MyFrame2(Frame):
            def __init__(self, param, kwparam):
                super().__init__()
                log.debug("param=%s" % param)
                log.debug("kwparam=%s" % kwparam)
        @MyFrame2('param_value', kwparam='kwparam_value')
        async def main():
            pass
        self.loop.run(main)
        self.assertLogEqual("""
            0.0: param=param_value
            0.0: kwparam=kwparam_value
        """)

    def test_Frame_current(self):
        test = self
        test.subframe_counter = 0
        @MyFrame
        async def frame(self):
            test.assertEqual(Frame._current, self)
            async_subframe() # Test passive async frame
            test.assertEqual(Frame._current, self)
            await async_subframe() # Test active async frame
            test.assertEqual(Frame._current, self)
            subframe() # Test passive frame
            test.assertEqual(Frame._current, self)
            @Frame
            async def remove_after(frame, seconds):
                await sleep(seconds)
                frame.remove()
            sf = subframe()
            remove_after(sf, 0.1)
            await sf # Test active frame
            test.assertEqual(Frame._current, self)
        @MyFrame
        async def async_subframe(self):
            test.assertEqual(Frame._current, self)
            await sleep()
            test.subframe_counter += 1
        @MyFrame
        def subframe(self):
            test.assertEqual(Frame._current, self)
            test.subframe_counter += 1
        self.loop.run(frame)
        test.assertEqual(test.subframe_counter, 4)

    def test_remove_self(self):
        @Frame
        def frame(self):
            log.debug("1")
            self.remove()
            log.debug("2") # Frame.remove() doesn't interrupt regular frame functions
        @Frame
        async def async_frame(self):
            log.debug("3")
            self.remove()
            log.debug("never reached") # Frame.remove() interrupts async frame functions
        self.loop.run(frame)
        self.loop.run(async_frame)
        self.assertLogEqual("""
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
            log.debug('Removing frame')
            frame.remove()
        @Frame
        async def main(self):
            self.p = None
            @Frame
            async def primitive_owner():
                self.p = MyPrimitive()
                await sleep(0.1)
                log.debug('Removing primitive')
            primitive_owner()

            remove_after(self, 0.3)
            a = (self.free | sleep(0.1))
            await a
            log.debug('Re-removing any_')
            test.assertEqual(a.remove(), False)

            s = sleep(0.1)
            a = (self.free & s)
            await a
            log.debug('Re-removing all_')
            test.assertEqual(a.remove(), False)

            log.debug('Re-removing event source')
            test.assertEqual(s.remove(), False)

            log.debug('Re-removing primitive')
            test.assertEqual(self.p.remove(), False)

            log.debug('Re-removing frame')
            test.assertEqual(self.remove(), False)
        self.loop.run(main)
        log.debug('done')
        self.assertLogEqual("""
            0.1: Removing primitive
            0.1: Re-removing any_
            0.3: Removing frame
            0.3: Re-removing all_
            0.3: Re-removing event source
            0.3: Re-removing primitive
            0.3: Re-removing frame
            0.3: done
        """)

    def test_awaited_by_multiple(self):
        @Frame
        async def waitfor(w):
            await w
        @Frame
        async def main1(self):
            w = wait(0.1, '1')
            await (w & w)
        self.loop.run(main1)
        @Frame
        async def main2(self):
            w = wait(0.1, '2')
            await (w | w)
        self.loop.run(main2)
        @Frame
        async def main3(self):
            w = sleep(0.1)
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 & a2)
        self.loop.run(main3)
        @Frame
        async def main4(self):
            w = wait(0.1, '3')
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 & a2)
        self.loop.run(main4)
        @Frame
        async def main5(self):
            w = wait(0.1, '4')
            a1 = waitfor(w)
            a2 = waitfor(w)
            await (a1 | a2)
        self.loop.run(main5)
        @Frame
        async def main6(self):
            s = sleep(0.1)
            await (s | s & s)
        self.loop.run(main6)

    def test_finished_before_await(self):
        @Frame
        async def main():
            s = sleep(0.1)
            w = wait(0.1, '1')
            log.debug((await sleep(0.2)).source)
            log.debug((await s).source)
            log.debug(await w)
            log.debug((await (s | w)).source)
            s_and_w = await (s & w)
            for k in sorted(s_and_w):
                v = s_and_w[k]
                log.debug("{}: {}".format(k, v))
            log.debug('done')
        self.loop.run(main)
        self.assertLogEqual("""
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
            log.debug("'%s' raised '%s' with args '%s'", e.sender, e.source, e.args)
            e = await ae
            log.debug("'%s' reraised '%s' with args '%s'", e.sender, e.source, e.args)

            post_event(0.1, ae)
            ae.post(self, 'my event args', 0.2)
            e = await ae
            log.debug("'%s' raised '%s' with args '%s'", e.sender, e.source, e.args)
            e = await ae
            log.debug("'%s' reraised '%s' with args '%s'", e.sender, e.source, e.args)

            if test.supports_invoke:
                threading.Thread(target=invoke_event, args=(0.1, ae)).start()
                threading.Thread(target=ae.invoke, args=(self, 'my event args', 0.2)).start()
                e = await ae
                log.debug("'%s' raised '%s' with args '%s'", e.sender, e.source, e.args)
                e = await ae
                log.debug("'%s' reraised '%s' with args '%s'", e.sender, e.source, e.args)
            else:
                await sleep(0.1)
                log.debug("'invoke_event' raised 'my event' with args 'my event args'")
                await sleep(0.1)
                log.debug("'main' reraised 'my event' with args 'my event args'")
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

        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 'send_event' raised 'my event' with args 'my event args'
            0.2: 'send_event' reraised 'my event' with args 'my event args'
            0.3: 'post_event' raised 'my event' with args 'my event args'
            0.4: 'main' reraised 'my event' with args 'my event args'
            0.5: 'invoke_event' raised 'my event' with args 'my event args'
            0.6: 'main' reraised 'my event' with args 'my event args'
        """)

    def test_exceptions(self):
        @Frame
        async def main():
            # Catch exception raised from active frame
            with self.assertRaises(ZeroDivisionError):
                await raise_immediately()
            with self.assertRaises(ZeroDivisionError):
                await (hold() | raise_immediately())
            with self.assertRaises(ZeroDivisionError):
                await (hold() & raise_immediately())
            log.debug(1)

            # Catch exception raised from active frame woken by event
            with self.assertRaises(ZeroDivisionError):
                await raise_delayed()
            with self.assertRaises(ZeroDivisionError):
                await (hold() | raise_delayed())
            with self.assertRaises(ZeroDivisionError):
                await (hold() & raise_delayed())
            log.debug(2)

            # Catch exception raised from passive frame
            with self.assertRaises(ZeroDivisionError):
                raise_immediately()
            with self.assertRaises(ZeroDivisionError):
                hold() | raise_immediately()
            with self.assertRaises(ZeroDivisionError):
                hold() & raise_immediately()
            log.debug(3)

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
        self.loop.run(main)
        self.assertLogEqual("""
            0.0: 1
            0.3: 2
            0.3: 3
            0.4: Passive frame exception caught: ZeroDivisionError()
            0.4: Passive frame exception caught: ZeroDivisionError()
            0.4: Passive frame exception caught: ZeroDivisionError()
        """)

    def test_animate(self):
        @Frame
        async def a():
            await animate(0.25, lambda f: log.debug(''), 0.1)
        @Frame
        async def main():
            await a()
        self.loop.run(main)
        self.assertLogEqual("""
            0.1
            0.2
            0.2
        """)

    def test_unfinished_await(self):
        @MyFrame
        async def frame():
            await subframe()
            await (subframe() | hold())
            await (subframe() & sleep())
        @MyFrame
        async def subframe():
            await sleep()
            await sleep()
        self.loop.run(frame)

    def test_rerun(self):
        @Frame
        async def main():
            await wait(0.1, 'main')
        @Frame
        async def raise_exception():
            raise ZeroDivisionError
        self.loop.run(main)
        self.loop.run(main)
        with self.assertRaises(ZeroDivisionError):
            self.loop.run(raise_exception)
        self.loop.run(main)
        self.assertLogEqual("""
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
        self.loop.run(main)

    def test_invalid_usage(self):
        @Frame
        def raise_already_running():
            self.loop.run(wait, 0.0, '')
        with self.assertRaisesRegex(InvalidOperationException, "Another event loop is already running"):
            self.loop.run(raise_already_running)
        with self.assertRaisesRegex(InvalidOperationException, "Can't call frame without a running event loop"):
            wait(0.0, '')

    def test_reawait(self):
        @Frame
        async def main():
            s1 = sleep(0.1)
            s2 = sleep(0.2)
            s3 = sleep(0.3)
            self.assertEqual((await (s1 | s2)).source, s1)
            log.debug('1')
            self.assertEqual((await (s2 | s3)).source, s2)
            log.debug('2')
            self.assertEqual(set([v.source for v in (await (s2 & s3)).values()]), set([s2, s3]))
            log.debug('3')
            await s1
            await s2
            await s3
            log.debug('4')
        self.loop.run(main)
        self.assertLogEqual("""
            0.1: 1
            0.2: 2
            0.3: 3
            0.3: 4
        """)

    def test_free(self):
        @Frame
        async def frame():
            sf = subframe()
            await sleep(0.1)
            sf.remove()

            subframe()
        @Frame
        async def subframe(self):
            log.debug('1')
            await self.free
            log.debug('2')
        self.loop.run(frame)
        self.assertLogEqual("""
            0.0: 1
            0.1: 2
            0.1: 1
            0.1: 2
        """)

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

if __name__ == "__main__":
    unittest.main()
