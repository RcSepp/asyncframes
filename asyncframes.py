import abc
import collections.abc
import inspect
import logging
import sys


log = logging.getLogger(__name__)
if False:
	log.setLevel(logging.DEBUG)


loghandler = logging.StreamHandler(sys.stdout)
loghandler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(message)s")
loghandler.setFormatter(formatter)
log.addHandler(loghandler)


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


class Awaitable(collections.abc.Awaitable):
	def __init__(self, name, signal=None, signal_sender=None):
		self.__name__ = name
		self._parent = None
		self._removed = False
		self._listeners = set()
		if signal:
			signal.connect(lambda e=None: Event(signal_sender, self, e).post())
	def remove(self):
		if self._removed:
			return False
		self._removed = True
		#log.debug("REMOVING {}".format(self))
		return True
	def __str__(self):
		return self.__name__
	def __repr__(self):
		return "<{}.{} object at 0x{:x}>".format(self.__module__, self.__name__, id(self))
	def __await__(self):
		if self._removed: # If this awaitable finished before being awaited
			raise StopIteration()
		while True:
			try:
				log.debug("{}await {}".format(str(Frame._current).ljust(10), self))
				self._listeners.add(Frame._current)
				msg = yield self
				self._listeners.remove(Frame._current)
				log.debug("{}await {} -> {}".format(str(Frame._current).ljust(10), self, msg))
				if isinstance(msg, Exception):
					raise msg
				#self.step(eventstack, eventstackptr)
			except StopIteration as stop:
				return stop.value
			except GeneratorExit:
				return None
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg and msg.target == self:
			#self.remove() # Don't remove primitive awaitables like events, since they may be raised multiple times
			stop = StopIteration()
			stop.value = msg
			raise stop
	def process(self, sender, msg):
		try:
			msg = self.step(sender, msg)
		except (StopIteration, GeneratorExit) as stop:
			if self._listeners:
				for listener in self._listeners.copy():
					listener.process(self, stop)
			else:
				return #raise stop
		else:
			if self._listeners:
				for listener in self._listeners.copy():
					listener.process(self, msg)
		# try:
		# 	self.step(eventstack, len(eventstack) - 1)
		# except (StopIteration, GeneratorExit):
		# 	pass
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

		# Adopt awaitables
		self._children = [awaitable for awaitable in awaitables if not awaitable._removed]
		for child in self._children: # Note: This loop also erases identical children
			if child._parent:
				child._parent._children.remove(child)
			child._parent = self

		self._results = {}


	def __await__(self):
		if self._removed: # If this awaitable finished before being awaited
			raise StopIteration()
		while True:
			try:
				log.debug("{}await {}".format(str(Frame._current).ljust(10), self))
				for child in self._children:
					child._listeners.add(self)
				self._listeners.add(Frame._current)
				msg = yield self
				self._listeners.remove(Frame._current)
				for child in self._children:
					child._listeners.remove(self)
				log.debug("{}await {} -> {}".format(str(Frame._current).ljust(10), self, msg))
				if isinstance(msg, Exception):
					raise msg
				#self.step(eventstack, eventstackptr)
			except StopIteration as stop:
				return stop.value
			except GeneratorExit:
				return None
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg is None:
			return self

		if isinstance(msg, Exception):
			self._results[sender] = msg.value

		if not self._children: # If all children finished and removed themselves from self._children
			self.remove()
			stop = StopIteration()
			stop.value = self._results.values()
			raise stop

		return self

	def remove(self):
		if not super().remove():
			return False
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self
		return True

class any_(Awaitable):
	def __init__(self, *awaitables):
		super().__init__("any({})".format(", ".join(str(a) for a in awaitables)))

		if any(awaitable._removed for awaitable in awaitables):
			super().remove()
			return

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)

		# Adopt awaitables
		self._children = list(awaitables)
		for child in self._children: # Note: This loop also erases identical children
			if child._parent:
				child._parent._children.remove(child)
			child._parent = self

	def __await__(self):
		if self._removed: # If this awaitable finished before being awaited
			raise StopIteration()
		while True:
			try:
				log.debug("{}await {}".format(str(Frame._current).ljust(10), self))
				for child in self._children:
					child._listeners.add(self)
				self._listeners.add(Frame._current)
				msg = yield self
				if isinstance(msg, Exception):
					raise msg
				self._listeners.remove(Frame._current)
				for child in self._children:
					child._listeners.remove(self)
				log.debug("{}await {} -> {}".format(str(Frame._current).ljust(10), self, msg))
				#self.step(eventstack, eventstackptr)
			except StopIteration as stop:
				return stop.value
			except GeneratorExit:
				return None
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg is None:
			return self

		if isinstance(msg, Exception):
			self.remove()
			raise msg

		return self

	def remove(self):
		if not super().remove():
			return False
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		#del self
		return True


class sleep(Awaitable):
	def __init__(self, seconds=0.0):
		if seconds < 0:
			raise ValueError()
		super().__init__("sleep({})".format(seconds))
		log.debug("{}{}".format(str(Frame._current).ljust(10), self))
		EventLoop._current.postevent(Event(None, self, None), delay=seconds)
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg and msg.target == self:
			self.remove()
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self

class hold(Awaitable):
	def __init__(self, seconds=0.0):
		super().__init__("hold()")
	def step(self, eventstack, eventstackptr):
		log.debug("{}{}.step({}, {})".format(str(Frame._current).ljust(10), self, eventstack, eventstackptr))
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

			# Activate parent
			Frame._current = self._parent

			if inspect.isawaitable(self._generator): # If framefunc is a coroutine
				# Start coroutine
				try:
					self.step(None, None)
				except (StopIteration, GeneratorExit):
					pass

	def step(self, sender, msg):
		if self._removed:
			raise StopIteration()
		if self._generator is None:
			return self

		# Activate self
		Frame._current = self

		# Advance generator
		try:
			log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
			awaitable = self._generator.send(msg)
			log.debug("{}{}.step({}) -> {}".format(str(Frame._current).ljust(10), self, msg, awaitable))
		except (StopIteration, GeneratorExit): # If done
			Frame._current = self._parent # Activate parent
			self.remove()
			raise

		# Activate parent
		Frame._current = self._parent

		return self

	def remove(self):
		if not super().remove():
			return False

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

		return True



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
