import collections.abc
import inspect
import sys
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer


class Awaitable(collections.abc.Awaitable):
	def __init__(self):
		self._parent = None
	def remove(self):
		pass
	def __await__(self):
		msg = None
		while True:
			if self._parent:
				self._parent._activechild = self
			try:
				msg = yield(self.step(msg))
			except StopIteration as stop:
				return stop.value
	def step(self, msg=None):
		if msg == self:
			stop = StopIteration()
			stop.value = self
			raise stop
		return self #TODO: Return value "self" not required
	def raise_event(self):
		update(self)
	def __and__(self, other):
		return and_(self, other)
	def __or__(self, other):
		return or_(self, other)

class and_(Awaitable):
	def __init__(self, *awaitables):
		super().__init__()

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = list(awaitables)

		# Adopt self._children
		for child in self._children:
			if child._parent:
				child._parent._children.remove(child)
			child._parent = self

		self.results = {}

	def step(self, msg=None):
		for child in self._children:
			try:
				self.results[child] = child.step(msg)
			except StopIteration as stop:
				self.results[child] = stop.value

		if self._children: # If some children aren't finished yet
			return None
		else: # If all children finished and removed themselves from self._children
			stop = StopIteration()
			stop.value = self.results.values()
			raise stop

	def remove(self):
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self

class or_(Awaitable):
	def __init__(self, *awaitables):
		super().__init__()

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = list(awaitables)

		# Adopt self._children
		for child in self._children:
			if child._parent:
				child._parent._children.remove(child)
			child._parent = self

		self.results = {}

	def step(self, msg=None):
		for child in self._children:
			child.step(msg)
		
		# If no child raised StopIteration
		return None

	def remove(self):
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self


class sleep(Awaitable):
	def __init__(self, seconds=0.0):
		super().__init__()
		self.non_blocking = seconds <= 0.0
		if not self.non_blocking:
			QTimer.singleShot(1000 * seconds, self.raise_event)
	def step(self, msg=None):
		if msg == self or self.non_blocking:
			stop = StopIteration()
			stop.value = self
			raise stop
		return self #TODO: Return value "self" not required

class hold(Awaitable):
	def raise_event():
		pass # hold can't be raised

# @types.coroutine
# def sleep(seconds):
# 	QTimer.singleShot(1000 * seconds, tick)
# 	yield 123


class Frame(Awaitable):
	_current = None

	def __new__(cls, *frameclassargs, **frameclasskwargs):
		def ___new__(framefunc):
			def create_frame(*frameargs, **framekwargs):
				frame = super(Frame, cls).__new__(cls)
				frame.__init__(*frameclassargs, **frameclasskwargs)
				frame.create(framefunc, *frameargs, **framekwargs)
				return frame
			return create_frame

		if len(frameclassargs) == 1 and not frameclasskwargs and callable(frameclassargs[0]): # If @frame was called without parameters
			framefunc = frameclassargs[0]
			frameclassargs = ()
			return ___new__(framefunc)
		else: # If @frame was called with parameters
			return ___new__

	def __init__(self):
		super().__init__()
		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = []
		self._activechild = None

		self._primitives = []

	def create(self, framefunc, *frameargs, **framekwargs):
		#self._framefunc = framefunc

		hasself = 'self' in inspect.signature(framefunc).parameters
		self._generator = framefunc(self, *frameargs, **framekwargs) if hasself else framefunc(*frameargs, **framekwargs)

	def step(self, msg=None):
		if self._generator is None:
			return None

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

	def remove(self):
		if self._generator:
			self._generator.close()
			self._generator = None
		while self._children:
			self._children[-1].remove()
		if self._parent:
			self._parent._children.remove(self)
		while self._primitives:
			self._primitives[-1].remove()
		#del self



def define_frame(*defineframeargs, **defineframekwargs):
	if len(defineframeargs) == 1 and not defineframekwargs and inspect.isclass(defineframeargs[0]): # If @define_frame was called without parameters
		frameclass = defineframeargs[0]
		defineframeargs = ()
		return frameclass
	else: # If @define_frame was called with parameters
		return lambda frameclass: frameclass


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

	Frame._current = None
	MAIN_FRAME = mainframe()
	if update():
		try:
			qt.exec_()
		except:
			print(traceback.format_exc())


class Primitive(object):
	def __init__(self, owner):
		# Validate parameters
		if not issubclass(owner, Frame):
			raise TypeError("'owner' must be of type Frame")

		# Find parent frame of class 'owner'
		self._owner = Frame._current
		while self._owner and not issubclass(type(self._owner), owner):
			self._owner = self._owner._parent
		if not self._owner:
			raise Exception(self.__class__.__name__ + " can't be defined outside " + owner.__name__)

		# Register with parent frame
		self._owner._primitives.append(self)

	def remove(self):
		self._owner._primitives.remove(self)


if __name__ == "__main__":
	@define_frame
	class MyFrame1(Frame):
		pass
	@define_frame
	class MyFrame2(Frame):
		pass

	class MyPrimitive(Primitive):
		def __init__(self):
			super().__init__(MyFrame1)

	@MyFrame1
	async def coroutine():
		other(0.1, '1')
		await other(0.2, '2')
		print('DONE')

	@MyFrame2
	async def other(seconds, name):
		p = MyPrimitive()
		await sleep(seconds)
		print(name)

	run(coroutine)
