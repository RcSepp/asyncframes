import abc
import collections.abc
import datetime
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
	def _run(self):
		raise NotImplementedError() # pragma: no cover
	@abc.abstractmethod
	def _stop(self):
		raise NotImplementedError() # pragma: no cover
	@abc.abstractmethod
	def _post(self, event, delay):
		raise NotImplementedError() # pragma: no cover

	def __init__(self):
		self.passive_frame_exception_handler = None

	def run(self, frame):
		if EventLoop._current is not None:
			raise Exception("Another event loop is already running")
		EventLoop._current = self

		try:
			self.mainframe = frame()
			if self.mainframe._generator is not None:
				self._run()
		finally:
			EventLoop._current = None
			Frame._current = None

	def sendevent(self, event):
		# Discard events sent after the event loop has been closed
		if self != EventLoop._current: return

		if event.target._listeners:
			def recursive_listener_search(awaitable, listeners):
				if awaitable._listeners:
					for listener in awaitable._listeners:
						recursive_listener_search(listener, listeners)
				else:
					listeners.add(awaitable)
			listeners = set()
			recursive_listener_search(event.target, listeners)
			log.debug("Event {} wakes up {}".format(event, listeners))
		else:
			log.debug("Ignoring event {}".format(event))

		try:
			event.target.process(event.target, event)
		except Exception as err:
			if self.passive_frame_exception_handler:
				self.passive_frame_exception_handler(err)
			else:
				raise

		if self.mainframe.removed: # If the main frame finished
			log.debug("Main frame finished")
			self._stop()
			return False

		return True

	def postevent(self, event, delay=0):
		# Discard events sent after the event loop has been closed
		if self != EventLoop._current: return

		self._post(event, delay)


class Awaitable(collections.abc.Awaitable):
	def __init__(self, name):
		self.__name__ = name
		self._parent = None
		self._removed = False
		self._result = None
		self._listeners = set()
	def remove(self):
		if self._removed:
			return False
		self._removed = True
		#log.debug("REMOVING {}".format(self))
		return True
	@property
	def removed(self):
		return self._removed
	def __str__(self):
		return self.__name__
	def __repr__(self):
		return "<{}.{} object at 0x{:x}>".format(self.__module__, self.__name__, id(self))
	def __await__(self):
		if self.removed: # If this awaitable already finished
			return self._result
		while True:
			try:
				listener = Frame._current
				self._listeners.add(listener)
				log.debug("{}await {}".format(str(listener).ljust(10), self))
				msg = yield self
				log.debug("{}await {} -> {}".format(str(listener).ljust(10), self, msg))
				if isinstance(msg, Exception):
					raise msg
			except (StopIteration, GeneratorExit):
				return self._result
			finally:
				self._listeners.remove(listener)
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg and msg.target == self:
			self._result = msg
			self.remove()
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self #TODO: Never reached
	def process(self, sender, msg):
		try:
			msg = self.step(sender, msg)
		except (StopIteration, GeneratorExit) as err:
			msg = err # Forward exception to listeners
		except Exception as err:
			if not self._listeners: raise
			msg = err # Forward exception to listeners
		if self._listeners:
			for listener in self._listeners.copy():
				listener.process(self, msg)
	def __and__(self, other):
		return all_(self, other)
	def __or__(self, other):
		return any_(self, other)

class AwaitableEvent(Awaitable):
	def __init__(self, name, signal=None, signal_sender=None):
		super().__init__(name)
		if signal:
			signal.connect(lambda e=None: Event(signal_sender, self, e).post())
	def remove(self):
		return True  # Don't remove awaitable events, since they may be raised multiple times

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

		self._result = {awaitable:awaitable._result for awaitable in awaitables if awaitable.removed}
		if len(self._result) == len(awaitables):
			super().remove()
			return

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)

		# Adopt awaitables
		self._children = [awaitable for awaitable in awaitables if not awaitable.removed]
		for child in self._children: # Note: This loop also erases identical children
			if child._parent:
				child._parent._children.remove(child)
			child._parent = self


	def __await__(self):
		if self.removed: # If this awaitable already finished
			return self._result
		while True:
			try:
				listener = Frame._current
				self._listeners.add(listener)
				for child in self._children:
					child._listeners.add(self)
				log.debug("{}await {}".format(str(listener).ljust(10), self))
				msg = yield self
				log.debug("{}await {} -> {}".format(str(listener).ljust(10), self, msg))
				if isinstance(msg, Exception):
					raise msg
			except (StopIteration, GeneratorExit):
				return self._result
			finally:
				self._listeners.remove(listener)
				for child in self._children:
					child._listeners.remove(self)
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg is None:
			return self #TODO: Never reached

		if isinstance(msg, Exception):
			if type(msg) == StopIteration:
				self._result[sender] = msg.value
			elif type(msg) != GeneratorExit:
				raise msg

		if not self._children: # If all children finished and removed themselves from self._children
			self.remove()
			stop = StopIteration()
			stop.value = self._result
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

		for awaitable in awaitables:
			if awaitable.removed:
				self._result = awaitable._result
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
		if self.removed: # If this awaitable already finished
			return self._result
		while True:
			try:
				listener = Frame._current
				self._listeners.add(listener)
				for child in self._children:
					child._listeners.add(self)
				log.debug("{}await {}".format(str(listener).ljust(10), self))
				msg = yield self
				log.debug("{}await {} -> {}".format(str(listener).ljust(10), self, msg))
				if isinstance(msg, Exception):
					raise msg
			except (StopIteration, GeneratorExit):
				return self._result
			finally:
				self._listeners.remove(listener)
				for child in self._children:
					child._listeners.remove(self)
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		if msg is None:
			return self #TODO: Never reached

		if isinstance(msg, Exception):
			if type(msg) == StopIteration:
				self._result = msg.value
			self.remove()
			raise msg

		return self #TODO: Never reached

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

class hold(Awaitable):
	def __init__(self, seconds=0.0):
		super().__init__("hold()")
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		return self # hold can't be raised

class animate(Awaitable):
	def __init__(self, seconds, callback):
		super().__init__("animate()")
		self.seconds = seconds
		self.callback = callback
		self.startTime = datetime.datetime.now()
		EventLoop._current.postevent(Event(None, self, None))
	def step(self, sender, msg):
		log.debug("{}{}.step({})".format(str(Frame._current).ljust(10), self, msg))
		t = (datetime.datetime.now() - self.startTime).total_seconds()

		if t >= self.seconds:
			self.callback(1.0)
			self._result = msg
			self.remove()
			stop = StopIteration()
			stop.value = msg
			raise stop
		else:
			self.callback(t / self.seconds)

			# Reraise event
			EventLoop._current.postevent(Event(None, self, None))


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

	def create(self, framefunc, *frameargs, **framekwargs):
		if framefunc and not self.removed and self._generator is None:
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
		if self.removed:
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
		except StopIteration as stop: # If done
			self._result = stop.value
			self.remove()
			raise
		except (GeneratorExit, Exception): # If done
			self.remove()
			raise
		finally:
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
