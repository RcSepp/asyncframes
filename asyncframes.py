import collections.abc
import inspect
import logging
import sys
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer


log = logging.getLogger(__name__)
if False:
	log.setLevel(logging.DEBUG)


loghandler = logging.StreamHandler(sys.stdout)
loghandler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(message)s")#('%(relativeCreated)d - %(name)s - %(levelname)s - %(message)s')
loghandler.setFormatter(formatter)
log.addHandler(loghandler)


class Awaitable(collections.abc.Awaitable):
	def __init__(self, name, signal=None, signal_sender=None):
		self.__name__ = name
		self._parent = None
		if signal:
			signal.connect(lambda e: Event(signal_sender, self, e).post())
	def remove(self):
		pass
	def __str__(self):
		return self.__name__
	def __repr__(self):
		return self.__name__
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
		if msg and msg.receiver == self:
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self
	def __and__(self, other):
		return all_(self, other)
	def __or__(self, other):
		return any_(self, other)

class Event():
	def __init__(self, sender, receiver, args):
		self.sender = sender
		self.receiver = receiver
		self.args = args

	def __str__(self):
		return str(self.receiver)

	def post(self):
		log.debug("Posting {}".format(self))
		try:
			awaitable = MAIN_FRAME.step(self)
		except StopIteration:
			QApplication.instance().exit()
			return False
		log.debug("Awaiting (active) {}".format(awaitable))
		return True

class all_(Awaitable):
	def __init__(self, *awaitables):
		super().__init__("all({})".format(", ".join(str(a) for a in awaitables)))

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
			return self
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

class any_(Awaitable):
	def __init__(self, *awaitables):
		super().__init__("any({})".format(", ".join(str(a) for a in awaitables)))

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
		return self

	def remove(self):
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self


class sleep(Awaitable):
	def __init__(self, seconds=0.0):
		if seconds < 0:
			raise ValueError()
		super().__init__("sleep({})".format(seconds))
		QTimer.singleShot(1000 * seconds, lambda: Event(None, self, None).post())
	def step(self, msg=None):
		if msg and msg.receiver == self:
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self

class hold(Awaitable):
	def __init__(self, seconds=0.0):
		super().__init__("hold()")
	def step(self, msg=None):
		pass # hold can't be raised
		return self

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
		super().__init__(self.__class__.__name__)
		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = []
		self._activechild = None

		self._primitives = []

	def create(self, framefunc, *frameargs, **framekwargs):
		self.__name__ += ' ' + framefunc.__name__
		self._removed = False
		
		# Activate self
		Frame._current = self

		hasself = 'self' in inspect.signature(framefunc).parameters
		self._generator = framefunc(self, *frameargs, **framekwargs) if hasself else framefunc(*frameargs, **framekwargs)

		# Actiivate parent
		Frame._current = self._parent

	def step(self, msg=None):
		if self._removed:
			raise StopIteration()
		if self._generator is None:
			return self

		# Activate self
		Frame._current = self

		# Advance generator
		try:
			result = self._generator.send(msg)
		except StopIteration: # If done
			self.remove()
			Frame._current = self._parent # Actiivate parent
			raise

		# Activate parent
		Frame._current = self._parent

		# Advance passive child frames
		for child in self._children:
			if child != self._activechild:
				try:
					awaitable = child.step(msg)
				except StopIteration as stop:
					child.remove()
					pass
				else:
					log.debug("Awaiting (passive) {}".format(awaitable))

		# Return iteration result of active child frame
		return result

	def remove(self):
		if not self._removed:
			self._removed = True
			if self._generator:
				self._generator.close()
				self._generator = None
			while self._children:
				self._children[-1].remove()
			if self._parent:
				self._parent._children.remove(self)
			while self._primitives:
				self._primitives[-1].remove()



def define_frame(*defineframeargs, **defineframekwargs):
	if len(defineframeargs) == 1 and not defineframekwargs and inspect.isclass(defineframeargs[0]): # If @define_frame was called without parameters
		frameclass = defineframeargs[0]
		defineframeargs = ()
		return frameclass
	else: # If @define_frame was called with parameters
		return lambda frameclass: frameclass


def run(mainframe):
	global MAIN_FRAME
	qt = QApplication.instance() or QApplication(sys.argv)

	try:
		import qdarkstyle
	except ImportError:
		pass
	else:
		qt.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

	Frame._current = None
	MAIN_FRAME = mainframe()
	if Event.post(None):
		try:
			qt.exec_()
		except:
			logging.exception(traceback.format_exc())


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
