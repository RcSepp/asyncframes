import collections.abc
import inspect
import sys
import types
import unittest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QObject


class Awaitable(collections.abc.Awaitable):
	def __and__(self, other):
		print(self)

class Awaitable(Awaitable):
	def __and__(self, other):
		return AndAwaitable(self, other)
	# def __or__(self, other):
	# 	return OrAwaitable(self, other)

class AndAwaitable(Awaitable):
	def __init__(self, a1, a2):
		self.a1 = a1
		self.a2 = a2

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = [a1, a2]
		if self.a1._parent:
			self.a1._parent._children.remove(a1)
		self.a1._parent = self
		if self.a2._parent:
			self.a2._parent._children.remove(a2)
		self.a2._parent = self
	def __await__(self):
		d1, d2 = False, False
		r1, r2 = None, None
		msg = None

		try:
			r1 = self.a1.step(msg)
		except StopIteration as stop:
			r1 = stop.value
			d1 = True
		try:
			r2 = self.a2.step(msg)
		except StopIteration as stop:
			r2 = stop.value
			d2 = True

		while not (d1 and d2):
			if self._parent:
				self._parent._activechild = self

			msg = yield((r1, r2))

			if not d1:
				try:
					r1 = self.a1.step(msg)
				except StopIteration as stop:
					r1 = stop.value
					d1 = True

			if not d2:
				try:
					r2 = self.a2.step(msg)
				except StopIteration as stop:
					r2 = stop.value
					d2 = True
		return (r1, r2)
	
	def remove(self):
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self


class sleep(Awaitable):
	def __init__(self, seconds):
		self._seconds = seconds #DELETE
		QTimer.singleShot(1000 * seconds, lambda: update(self))
	def __await__(self):
		msg = yield(self) #TODO: Value sended by yield (self) not required
		while msg != self:
			#print('self: {} != yield: {}'.format(self._seconds, msg._seconds if msg else msg))
			msg = yield(self) #TODO: Value sended by yield (self) not required
		#print('self: {} == yield: {}'.format(self._seconds, msg._seconds if msg else msg))

# @types.coroutine
# def sleep(seconds):
# 	QTimer.singleShot(1000 * seconds, tick)
# 	yield 123


class Frame(Awaitable):
	_current = None

	def __init__(self, framefunc, *frameargs, **framekwargs):
		self._framefunc = framefunc
		self.__name__ = framefunc.__name__
		#print("creating " + self.__name__)

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = []
		self._activechild = None

		hasself = 'self' in inspect.signature(self._framefunc).parameters
		self._generator = self._framefunc(self, *frameargs, **framekwargs) if hasself else self._framefunc(*frameargs, **framekwargs)

	def step(self, msg=None):
		#if self._generator is None:
		#	return None

		# Activate self
		Frame._current = self

		# Advance generator
		try:
			result = self._generator.send(msg)
		except StopIteration: # If done
			self.remove()
			Frame._current = self._parent # Actiivate parent
			raise

		# Actiivate parent
		Frame._current = self._parent

		# Advance passive child frames
		for child in self._children:
			if child != self._activechild:
				try:
					child.step(msg)
				except StopIteration:
					pass # Ignore child-frame-done exception, because child removes itself from self._children

		# Return iteration result of active child frame
		return result

	def __await__(self):
		msg = None
		while True:
			#print("awaiting " + self.__name__)
			if self._parent:
				self._parent._activechild = self

			#yield self.step()
			try:
				msg = yield(self.step(msg))
			except StopIteration as stop:
				return stop.value

	def remove(self):
		self._generator.close()
		#self._generator = None
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self



def define_frame(*defineframeargs, **defineframekwargs):
	def _define_frame(frameclass):
		def create_framefactory(*frameclassargs, **frameclasskwargs):
			def _create_framefactory(framefunc):
				def create_frame(*frameargs, **framekwargs):
					return frameclass(framefunc, *frameargs, **framekwargs)
					# frameinstance = frameclass(frame)
					# await frameinstance.run(*frameargs, **framekwargs)
					# frameinstance.remove()
				return create_frame

			if len(frameclassargs) == 1 and not frameclasskwargs and callable(frameclassargs[0]): # If @frame was called without parameters
				framefunc = frameclassargs[0]
				frameclassargs = ()
				return _create_framefactory(framefunc)
			else: # If @frame was called with parameters
				return _create_framefactory
		return create_framefactory

	if len(defineframeargs) == 1 and not defineframekwargs and inspect.isclass(defineframeargs[0]): # If @define_frame was called without parameters
		frameclass = defineframeargs[0]
		defineframeargs = ()
		return _define_frame(frameclass)
	else: # If @define_frame was called with parameters
		return _define_frame

@define_frame
class MyFrame(Frame):
	def __init__(self, framefunc, *frameargs, **framekwargs):
		super().__init__(framefunc, *frameargs, **framekwargs)


@MyFrame
async def coroutine():
	other(0.1, '1')
	await other(0.2, '2')
	print('DONE')

@MyFrame
async def other(seconds, name):
	await sleep(seconds)
	print(name)





def update(awaitable=None):
	try:
		MAIN_FRAME.step(awaitable)
	except StopIteration:
		QApplication.instance().exit()
		return False
	return True

def run(mainframe):
	global MAIN_FRAME
	qt = QApplication.instance() or QApplication(sys.argv)

	MAIN_FRAME = mainframe()
	if update():
		try:
			qt.exec_()
		except:
			print(traceback.format_exc())

#run(coroutine)


