import datetime
import io
import logging
import sys
import unittest
from PyQt5.QtWidgets import QApplication
from asyncframes import run, sleep, define_frame, Frame, Primitive

# def log(msg=None):
# 	t = (datetime.datetime.now() - starttime).total_seconds()
# 	if msg:
# 		print(round(t, 1), ": ", msg, sep='')
# 	else:
# 		print(round(t, 1))

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

		# Run an empty frame to perform one time initialization
		@MyFrame
		async def emptyframe():
			pass
		run(emptyframe)
	
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
		self.assertEqual(self.logstream.getvalue(), expected)

	def test_howtoyield_1(self):
		@MyFrame
		async def main():
			wait(0.1, '1')
			await wait(0.2, '2')
		run(main)
		self.assertLogEqual("""
			0.1: 1
			0.2: 2
		""")

	def test_howtoyield_2(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
			await wait(0.2, '2')
		run(main)
		self.assertLogEqual("""
			0.1: 1
			0.3: 2
		""")

	def test_howtoyield_3(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
			wait(0.2, '2')
		run(main)
		self.assertLogEqual("""
			0.1: 1
		""")

	def test_howtoyield_4(self):
		@MyFrame
		async def main():
			wait(0.1, '1')
			wait(0.2, '2')
		run(main)
		self.assertLogEqual("""
		""")

	def test_howtoyield_5(self):
		@MyFrame
		async def main():
			w1 = wait(0.1, '1')
			w2 = wait(0.2, '2')
			await (w1 & w2)
		run(main)
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
		run(main)
		self.assertLogEqual("""
			0.1: 1
		""")

	def test_frame_result(self):
		@MyFrame
		async def main():
			log.debug(await wait(0.1, '1'))
		run(main)
		self.assertLogEqual("""
			0.1: 1
			0.1: some result
		""")
	
	def test_blocking_sleep(self):
		@MyFrame
		async def main():
			log.debug((await sleep(0.1)).args)
		run(main)
		self.assertLogEqual("""
			0.1: None
		""")
	
	def test_non_blocking_sleep(self):
		@MyFrame
		async def main():
			log.debug((await sleep(0)).args)
		run(main)
		self.assertLogEqual("""
			0.0: None
		""")

	def test_staticmethod(self):
		@MyFrame
		async def main():
			MyFrame.mystaticmethod()
		run(main)
		self.assertLogEqual("""
			0.0: static method called
		""")

	def test_classvar(self):
		@MyFrame
		async def main():
			log.debug(MyFrame.classvar)
		run(main)
		self.assertLogEqual("""
			0.0: class variable
		""")

	def test_primitive(self):
		@MyFrame
		async def f1():
			MyPrimitive()
		run(f1)

		@MyFrame2
		async def f2():
			MyPrimitive()
		with self.assertRaises(Exception):
			run(f2)

		@MyFrame
		async def f3():
			f2()
		run(f3)

		with self.assertRaises(Exception):
			MyPrimitive()

if __name__ == "__main__":
	unittest.main()
