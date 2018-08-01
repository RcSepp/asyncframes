import datetime
import io
import sys
import unittest
from PyQt5.QtWidgets import QApplication
from asyncframes import run, sleep, define_frame, Frame, Primitive

def log(msg):
	t = (datetime.datetime.now() - starttime).total_seconds()
	print(round(t, 1), ": ", msg, sep='')

@define_frame
class MyFrame(Frame):
	@staticmethod
	def mystaticmethod():
		print('static method called!')
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
	log(name)
	return "some result"

class Tests (unittest.TestCase):
	def setUp(self):
		QApplication.instance() or QApplication(sys.argv)
		self.held, sys.stdout = sys.stdout, io.StringIO()

		global starttime
		starttime = datetime.datetime.now()

	def test_howtoyield_1(self):
		@MyFrame
		async def main():
			wait(0.1, '1')
			await wait(0.2, '2')
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '0.1: 1\n0.2: 2\n')

	def test_howtoyield_2(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
			await wait(0.2, '2')
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '0.1: 1\n0.3: 2\n')

	def test_howtoyield_3(self):
		@MyFrame
		async def main():
			await wait(0.1, '1')
			wait(0.2, '2')
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '0.1: 1\n')

	def test_howtoyield_4(self):
		@MyFrame
		async def main():
			wait(0.1, '1')
			wait(0.2, '2')
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '')

	def test_howtoyield_5(self):
		@MyFrame
		async def main():
			w1 = wait(0.1, '1')
			w2 = wait(0.2, '2')
			await (w1 & w2)
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '0.1: 1\n0.2: 2\n')

	def test_howtoyield_6(self):
		@MyFrame
		async def main():
			w1 = wait(0.1, '1')
			w2 = wait(0.2, '2')
			await (w1 | w2)
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '0.1: 1\n')

	def test_foo(self):
		@MyFrame
		async def main():
			print(await wait(0.1, '1'))
		run(main)
		self.assertEqual(sys.stdout.getvalue(), '0.1: 1\nsome result\n')

	def test_staticmethod(self):
		@MyFrame
		async def main():
			MyFrame.mystaticmethod()
		run(main)
		self.assertEqual(sys.stdout.getvalue(), 'static method called!\n')

	def test_classvar(self):
		@MyFrame
		async def main():
			print(MyFrame.classvar)
		run(main)
		self.assertEqual(sys.stdout.getvalue(), 'class variable\n')

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
