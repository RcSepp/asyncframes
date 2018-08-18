import datetime
import io
import logging
import unittest
from asyncframes import sleep, define_frame, AwaitableEvent, Event, Frame, Primitive
from asyncframes.pyqt5_eventloop import EventLoop

@define_frame
class MyFrame(Frame):
	@staticmethod
	def mystaticmethod():
		log.debug('static method called')
	classvar = 'class variable'

@define_frame
class MyFrame2(Frame):
	pass

class MyPrimitive(Primitive):
	def __init__(self):
		super().__init__(MyFrame)

@MyFrame
async def wait(seconds, name):
	result = await sleep(seconds)
	log.debug(name)
	return "some result"

class Tests (unittest.TestCase):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.loop = EventLoop()

	def setUp(self):
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
				return str(round(t, 1)) + ": " + msg if msg else str(round(t, 1))
		loghandler.setFormatter(TimedFormatter("%(message)s"))
		log.addHandler(loghandler)

	def assertLogEqual(self, expected):
		expected = expected.strip('\n').replace('\t', '') # Remove leading and trailing empty lines and tab stops
		self.assertEqual(expected, self.logstream.getvalue())

	def test_simple(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
		self.loop.run(main)
		self.assertLogEqual("""
			0.1: 1
		""")

	def test_regular_function_mainframe(self):
		@MyFrame
		def main():
			pass
		self.loop.run(main)

	def test_negative_sleep_duration(self):
		@MyFrame
		async def main():
			with self.assertRaises(ValueError):
				sleep(-1)
		self.loop.run(main)

	def test_howtoyield_1(self):
		@MyFrame
		async def main():
			wait(0.1, '1')
			await wait(0.2, '2')
		self.loop.run(main)
		self.assertLogEqual("""
			0.1: 1
			0.2: 2
		""")

	def test_howtoyield_2(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
			await wait(0.2, '2')
		self.loop.run(main)
		self.assertLogEqual("""
			0.1: 1
			0.3: 2
		""")

	def test_howtoyield_3(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
			wait(0.2, '2')
		self.loop.run(main)
		self.assertLogEqual("""
			0.1: 1
		""")

	def test_howtoyield_4(self):
		@MyFrame
		async def main():
			wait(0.1, '1')
			wait(0.2, '2')
		self.loop.run(main)
		self.assertLogEqual("""
		""")

	def test_howtoyield_5(self):
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

	def test_howtoyield_6(self):
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
		@MyFrame
		async def f1():
			MyPrimitive()
		self.loop.run(f1)

		@MyFrame2
		async def f2():
			MyPrimitive()
		with self.assertRaises(Exception):
			self.loop.run(f2)

		@MyFrame
		async def f3():
			f2()
		self.loop.run(f3)

		with self.assertRaises(Exception):
			MyPrimitive()

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
			log.debug((await sleep(0.2)).target)
			log.debug((await s).target)
			log.debug(await w)
			log.debug((await (s | w)).target)
			for k, v in (await (s & w)).items():
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
		@Frame
		async def main():
			ae = AwaitableEvent('my event')
			raise_event(0.1, ae)
			e = await ae
			log.debug("'%s' raised '%s' with args '%s'", e.sender, e.target, e.args)
		@Frame
		async def raise_event(self, seconds, awaitable_event):
			await sleep(seconds)
			Event(self, awaitable_event, 'my event args').process()

		self.loop.run(main)
		self.assertLogEqual("""
			0.1: 'raise_event' raised 'my event' with args 'my event args'
		""")

if __name__ == "__main__":
	unittest.main()
