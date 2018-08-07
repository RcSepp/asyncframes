import abc
import collections.abc
import inspect


class EventLoop(metaclass=abc.ABCMeta):
	_current = None

	@abc.abstractmethod
	def run(self, frame):
		raise NotImplementedError()
	@abc.abstractmethod
	def sendevent(self, event):
		raise NotImplementedError()
	@abc.abstractmethod
	def postevent(self, event, delay=0):
		raise NotImplementedError()
	@abc.abstractmethod
	def register_frame(self, frame, awaitable):
		raise NotImplementedError()


class Awaitable(collections.abc.Awaitable):
	def __init__(self, name, signal=None, signal_sender=None):
		self.__name__ = name
		self._parent = None
		if signal:
			signal.connect(lambda e=None: Event(signal_sender, self, e).post())
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
				msg = yield self.step(msg)
			except StopIteration as stop:
				return stop.value
			except GeneratorExit:
				return None
	def step(self, msg=None):
		if msg and msg.target == self:
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self
	def __and__(self, other):
		return all_(self, other)
	def __or__(self, other):
		return any_(self, other)

class Event():
	def __init__(self, sender, target, args):
		self.sender = sender
		self.target = target
		self.args = args

	def __str__(self):
		return str(self.target)

	def post(self):
		EventLoop._current.postevent(self)

	def process(self):
		return EventLoop._current.sendevent(self)

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

		self._results = {}
		self._frame_register = {}
		for child in self._children:
			try:
				awaitable = child.step(None)
			except (StopIteration, GeneratorExit):
				raise Exception("This should never be reached, because child.step(None) should only return awaitable and not finish.")
			else:
				self._frame_register[awaitable] = child

	def step(self, msg=None):
		if msg is None:
			return self._frame_register.keys()
		try:
			child = self._frame_register.pop(msg.target)
		except KeyError:
			return self._frame_register.keys()
		else:
			try:
				awaitable = child.step(msg)
			except StopIteration as stop:
				self._results[child] = stop.value
			except GeneratorExit:
				self._results[child] = None
			else:
				self._frame_register[awaitable] = child

		if self._children: # If some children aren't finished yet
			return self._frame_register.keys()
		else: # If all children finished and removed themselves from self._children
			stop = StopIteration()
			stop.value = self._results.values()
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

		self._results = {}
		self._frame_register = {}
		for child in self._children:
			try:
				awaitable = child.step(None)
			except (StopIteration, GeneratorExit):
				raise Exception("This should never be reached, because child.step(None) should only return awaitable and not finish.")
			else:
				self._frame_register[awaitable] = child

	def step(self, msg=None):
		if msg is None:
			return self._frame_register.keys()
		try:
			child = self._frame_register.pop(msg.target)
		except KeyError:
			return self._frame_register.keys()
		else:
			awaitable = child.step(msg)

			# If child didn't raise StopIteration or GeneratorExit
			self._frame_register[awaitable] = child
			return self._frame_register.keys()

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
		EventLoop._current.postevent(Event(None, self, None), delay=seconds)
	def step(self, msg=None):
		if msg and msg.target == self:
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self

class hold(Awaitable):
	def __init__(self, seconds=0.0):
		super().__init__("hold()")
	def step(self, msg=None):
		return self # hold can't be raised


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
		self._generator = None
		self._removed = False

	def create(self, framefunc, *frameargs, **framekwargs):
		if not self._removed and self._generator is None:
			self.__name__ = framefunc.__name__

			# Activate self
			Frame._current = self

			hasself = 'self' in inspect.signature(framefunc).parameters
			self._generator = framefunc(self, *frameargs, **framekwargs) if hasself else framefunc(*frameargs, **framekwargs)

			if inspect.isawaitable(self._generator):
				# Start coroutine
				try:
					awaitable = self._generator.send(None)
				except (StopIteration, GeneratorExit): # If coroutine is done
					Frame._current = self._parent # Activate parent
					self.remove()
				else: # If coroutine isn't done
					EventLoop._current.register_frame(self, awaitable) # Register self in event loop

			# Activate parent
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
			result = self._generator.send(None if self._generator.cr_await is None else msg)
		except (StopIteration, GeneratorExit): # If done
			Frame._current = self._parent # Activate parent
			self.remove()
			raise

		# Activate parent
		Frame._current = self._parent

		# # Advance passive child frames
		# for child in self._children:
		# 	if child != self._activechild:
		# 		try:
		# 			awaitable = child.step(msg)
		# 		except (StopIteration, GeneratorExit):
		# 			child.remove()
		# 			pass

		# Return iteration result of active child frame
		return result

	def remove(self):
		if not self._removed:
			self._removed = True

			# Remove child frames
			while self._children:
				self._children[-1].remove()

			# Remove self from parent frame
			if self._parent:
				self._parent._children.remove(self)

			# Remove primitives
			while self._primitives:
				self._primitives[-1].remove()

			# Post frame removed event
			Event(self, self, None).post()
			
			# Stop framefunc
			if self._generator: # If framefunc is a coroutine
				if self._generator.cr_running:
					# Calling coroutine.close() from within the coroutine is illegal, so we throw a GeneratorExit manually instead
					self._generator = None
					raise GeneratorExit()
				else:
					self._generator.close()
					self._generator = None



def define_frame(*defineframeargs, **defineframekwargs):
	if len(defineframeargs) == 1 and not defineframekwargs and inspect.isclass(defineframeargs[0]): # If @define_frame was called without parameters
		frameclass = defineframeargs[0]
		defineframeargs = ()
		return frameclass
	else: # If @define_frame was called with parameters
		return lambda frameclass: frameclass


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
