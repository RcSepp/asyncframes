# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import abc
import collections.abc
import datetime
import enum
import inspect
import logging
import sys
import threading


__all__ = [
    'all_', 'animate', 'any_', 'Awaitable', 'Event', 'AbstractEventLoop',
    'EventSource', 'Frame', 'FrameStartupBehaviour', 'InvalidOperationException',
    'hold', 'Primitive', 'sleep'
]
__version__ = '1.1.0'


class ThreadLocals(threading.local):
    def __init__(self):
        self.__dict__['_current_eventloop'] = None
        self.__dict__['_current_frame'] = None
_THREAD_LOCALS = ThreadLocals()

class FrameStartupBehaviour(enum.Enum):
    delayed = enum.auto()
    immediate = enum.auto()

class InvalidOperationException(Exception):
    """Raised when operations are performed out of context.

    Args:
        msg (str): Human readable string describing the exception
    """

    def __init__(self, msg):
        super().__init__(msg)

class AbstractEventLoop(metaclass=abc.ABCMeta):
    """Abstract base class of event loops."""

    @abc.abstractmethod
    def _run(self):
        raise NotImplementedError # pragma: no cover
    @abc.abstractmethod
    def _stop(self):
        raise NotImplementedError # pragma: no cover
    @abc.abstractmethod
    def _post(self, delay, callback, args):
        raise NotImplementedError # pragma: no cover
    def _invoke(self, delay, callback, args):
        logging.warning("Thread-safe event posting not available for this event loop. Falling back to non-thread-safe event posting") # pragma: no cover
        self._post(delay, callback, args) # pragma: no cover

    def __init__(self):
        self.mainframe = None
        self.passive_frame_exception_handler = None

    def run(self, frame, *frameargs, **framekwargs):
        if _THREAD_LOCALS._current_eventloop is not None:
            raise InvalidOperationException("Another event loop is already running")
        _THREAD_LOCALS._current_eventloop = self

        try:
            self.mainframe = frame(*frameargs, **framekwargs)
            if not self.mainframe.removed:
                self.mainframe._listeners.add(self) # Listen to mainframe finished event
                self._run()
        finally:
            self.mainframe = None
            _THREAD_LOCALS._current_eventloop = None
            _THREAD_LOCALS._current_frame = None

    def sendevent(self, event):
        # Discard events sent after the event loop has been closed
        if self != _THREAD_LOCALS._current_eventloop: return

        # Save current frame, since it will be modified inside Awaitable.process()
        currentframe = _THREAD_LOCALS._current_frame

        try:
            event.source.process(event.source, event)
        except Exception as err:
            if self.passive_frame_exception_handler:
                self.passive_frame_exception_handler(err)
            else:
                raise # pragma: no cover
        finally:
            # Restore current frame
            _THREAD_LOCALS._current_frame = currentframe

        return True

    def postevent(self, event, delay=0):
        # Discard events sent after the event loop has been closed
        if self != _THREAD_LOCALS._current_eventloop: return

        self._post(delay, self.sendevent, (event,))

    def invokeevent(self, event, delay=0):
        self._invoke(delay, self.sendevent, (event,))

    def _start_coroutine(self, frame):
        # Save current frame, since it will be modified inside Awaitable.process()
        currentframe = _THREAD_LOCALS._current_frame

        try:
            frame.process(None, None)
        except Exception as err:
            if self.passive_frame_exception_handler:
                self.passive_frame_exception_handler(err)
            else:
                raise # pragma: no cover
        finally:
            # Restore current frame
            _THREAD_LOCALS._current_frame = currentframe

    def process(self, sender, msg):
        if sender == self.mainframe: # If mainframe finished, ...
            sender._listeners.remove(self) # Stop monitoring mainframe
            self._stop() # Stop event loop


class Awaitable(collections.abc.Awaitable):
    """An awaitable frame or event source.

    Every node in the frame hierarchy is a subclass of `Awaitable`. An awaitable has a `__name__`,
    a parent awaitable (None, if the awaitable is the main frame), a list of child awaitables and
    a result, that gets set when the awaitable finishes.

    Args:
        name (str): The name of the awaitable
    """

    def __init__(self, name):
        self.__name__ = name
        self._parent = None
        self._removed = False
        self._result = None
        self._listeners = set()

    def remove(self):
        """Remove this awaitable from the frame hierarchy.

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        if self._removed:
            return False
        self._removed = True
        del self
        return True

    @property
    def removed(self):
        """Boolean property, indicating whether this awaitable has been removed from the frame hierarchy."""
        return self._removed

    def __str__(self):
        """Human readable representation of this frame."""
        return self.__name__

    def __repr__(self):
        return "<{}.{} object at 0x{:x}>".format(self.__module__, self.__name__, id(self))
    
    def __lt__(self, other):
        """Make awaitables sortable by name."""
        return self.__name__ < other.__name__

    def __await__(self):
        if self.removed: # If this awaitable already finished
            return self._result
        try:
            while True:
                msg = yield self
                if isinstance(msg, BaseException):
                    raise msg
        except (StopIteration, GeneratorExit):
            return self._result
        finally:
            self._listeners.clear()

    @abc.abstractmethod
    def step(self, sender, msg):
        raise NotImplementedError # pragma: no cover

    def process(self, sender, msg):
        """Propagate an event from its source and along awaiting nodes through the frame hierarchy.

        Args:
            sender (Awaitable): The source of the event or an awaited node that woke up
            msg: The incomming event or propagated message
        """

        _THREAD_LOCALS._current_frame = self # Activate self
        try:
            self.step(sender, msg)
        except BaseException as msg:
            if self._listeners:
                for listener in self._listeners.copy():
                    listener.process(self, msg)
            elif type(msg) != StopIteration and type(msg) != GeneratorExit:
                raise

    def __and__(self, other):
        """Register A & B as shortcut for all_(A, B)

        Args:
            other (Awaitable): The other awaitable

        Returns:
            all_: A frame awaiting `self` and `other`
        """

        return all_(self, other)
    def __or__(self, other):
        """Register A | B as shortcut for any_(A, B)

        Args:
            other (Awaitable): The other awaitable

        Returns:
            any_: A frame awaiting `self` and `other`
        """

        return any_(self, other)

class EventSource(Awaitable):
    """An awaitable emitter of events.

    Instantiate or overload this class to implement new events.
    Each type of event should be emitted by exactly one event source.
    For example, key-up and key-down events should be implemented by two separate event sources.
    Event sources represent leave nodes in the frame hierarchy.

    Args:
        name (str): The name of the event
        autoremove (bool, optional): Defaults to False. If `True`, removes the source after it has been resumed by an event
    """

    def __init__(self, name, autoremove=False):
        super().__init__(name)
        self.autoremove = autoremove
        self.eventloop = _THREAD_LOCALS._current_eventloop

    def remove(self):
        """Remove this awaitable from the frame hierarchy.

        If `autoremove` is False, this function is supressed

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        return super().remove() if self.autoremove else False

    def __bool__(self):
        return self._removed

    def step(self, sender, msg):
        """Handle incoming events.

        Args:
            sender (EventSource): The source of the event. This value is always identical to `self`
            msg (Event): The incomming event

        Raises:
            StopIteration: If the incoming event should wake up awaiting frames, raise a StopIteration with `value` set to the event
        """

        self._result = msg
        self.remove()
        stop = StopIteration()
        stop.value = msg
        raise stop

    def send(self, sender, args=None):
        """Dispatch and immediately process an event.

        Args:
            sender: The entity triggering the event, for example, the button instance on a button-press event
            args (optional): Defaults to None. Event arguments, for example, the progress value on a progress-update event
        """

        _THREAD_LOCALS._current_eventloop.sendevent(Event(sender, self, args))

    def post(self, sender, args=None, delay=0):
        """Enqueue an event in the event loop.

        Args:
            sender: The entity triggering the event, for example, the button instance on a button-press event
            args (optional): Defaults to None. Event arguments, for example, the progress value on a progress-update event
            delay (float, optional): Defaults to 0. The time in seconds to wait before posting the event
        """

        _THREAD_LOCALS._current_eventloop.postevent(Event(sender, self, args), delay)

    def invoke(self, sender, args=None, delay=0):
        """Enqueue an event in the event loop from a different thread.

        Args:
            sender: The entity triggering the event, for example, the button instance on a button-press event
            args (optional): Defaults to None. Event arguments, for example, the progress value on a progress-update event
            delay (float, optional): Defaults to 0. The time in seconds to wait before invoking the event
        """

        self.eventloop.invokeevent(Event(sender, self, args), delay)

class Event():
    """Data structure, containing information about the occurance of an event.

    Args:
        sender: The entity triggering the event, for example, the button instance on a button-press event
        source (EventSource): The awaitable class that dispached this event
        args: Event arguments, for example, the progress value on a progress-update event
    """

    def __init__(self, sender, source, args):
        self.sender = sender
        self.source = source
        self.args = args

    def __str__(self):
        return str(self.source)

class all_(Awaitable):
    """An awaitable that blocks the awaiting frame until all passed awaitables have woken up.

    Args:
        *awaitables (Awaitable[]): A list of all awaitables to await
    """

    def __init__(self, *awaitables):
        super().__init__("all({})".format(", ".join(str(a) for a in awaitables)))

        self._awaitables = set()
        self._result = {}
        for awaitable in awaitables:
            if awaitable.removed:
                self._result[awaitable] = awaitable._result
            else:
                self._awaitables.add(awaitable)
                awaitable._listeners.add(self)

        if len(self._result) == len(awaitables):
            super().remove()
            return

        self._parent = _THREAD_LOCALS._current_frame
        if self._parent:
            self._parent._children.append(self)

    def step(self, sender, msg):
        """Respond to an awaking child.

        Args:
            sender (Awaitable): The awaking child
            msg (BaseException): A StopIteration exception with the awaking child's result or an exception raised in a child frame

        Raises:
            StopIteration: Once all children woke up, this raises a StopIteration with `value` set to a dict of all children's results
            BaseException: If msg is an Exception other than GeneratorExit or StopIteration, the exception is re-raised
        """

        if isinstance(msg, BaseException):
            self._awaitables.remove(sender)
            sender._listeners.remove(self)
            if type(msg) == StopIteration:
                self._result[sender] = msg.value
            elif type(msg) != GeneratorExit:
                raise msg

        if not self._awaitables:
            self.remove()
            stop = StopIteration()
            stop.value = self._result
            raise stop

    def remove(self):
        """Remove this awaitable from the frame hierarchy.

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        if not super().remove():
            return False
        for awaitable in self._awaitables:
            awaitable._listeners.remove(self)
        self._awaitables.clear()
        if self._parent:
            self._parent._children.remove(self)
        return True

class any_(Awaitable):
    """An awaitable that blocks the awaiting frame until any of the passed awaitables wakes up.

    Args:
        *awaitables (Awaitable[]): A list of all awaitables to await
    """

    def __init__(self, *awaitables):
        super().__init__("any({})".format(", ".join(str(a) for a in awaitables)))

        self._awaitables = set()
        for awaitable in awaitables:
            if awaitable.removed:
                self._result = awaitable._result
                super().remove()
                return
            else:
                self._awaitables.add(awaitable)
                awaitable._listeners.add(self)

        self._parent = _THREAD_LOCALS._current_frame
        if self._parent:
            self._parent._children.append(self)

    def step(self, sender, msg):
        """Respond to an awaking child.

        Args:
            sender (Awaitable): The awaking child
            msg (BaseException): A StopIteration exception with the awaking child's result or an exception raised in a child frame

        Raises:
            StopIteration: If msg indicates an awaking child, store its result as this frame's result
            BaseException: Forward any exceptions
        """

        if isinstance(msg, BaseException):
            if type(msg) == StopIteration:
                self._result = msg.value
            self.remove()
            raise msg

    def remove(self):
        """Remove this awaitable from the frame hierarchy.

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        if not super().remove():
            return False
        for awaitable in self._awaitables:
            awaitable._listeners.remove(self)
        self._awaitables.clear()
        if self._parent:
            self._parent._children.remove(self)
        return True


class sleep(EventSource):
    """An awaitable used for suspending execution by the specified amount of time.

    A duration of 0 seconds will resume the awaiting frame as soon as possible.
    This is useful to implement non-blocking loops.

    Args:
        seconds (float, optional): Defaults to 0. The duration to wait
    """

    def __init__(self, seconds=0.0):
        super().__init__("sleep({})".format(seconds), autoremove=True)

        # Raise event
        _THREAD_LOCALS._current_eventloop.postevent(Event(self, self, None), delay=max(0, seconds))

class hold(EventSource):
    """An awaitable used for suspending execution indefinitely.

    Frames are automatically removed when the frame coroutine finishes.
    If you would like the frame to remain open until it is removed, write `await hold()` at the end of the coroutine.
    """

    def __init__(self):
        super().__init__("hold()", autoremove=True)
    def step(self, sender, msg):
        """ Ignore any incoming events."""

        pass

class animate(EventSource):
    """An awaitable used for periodically calling a callback function for the specified amount of time.

    Args:
        seconds (float): The duration of the animation
        callback (Callable[float, None]): The function to be called on every iteration. The first parameter of `callback` indicates animation progress between 0 and 1
        interval (float, optional): Defaults to 0.0. The minimum time in seconds between two consecutive calls of the callback
    """

    def __init__(self, seconds, callback, interval=0.0):
        super().__init__("animate()", autoremove=True)
        self.seconds = seconds
        self.callback = callback
        self.interval = interval
        self.startTime = datetime.datetime.now()
        self._final_event = False

        # Raise event
        _THREAD_LOCALS._current_eventloop.postevent(Event(self, self, None), delay=interval)

    def step(self, sender, msg):
        """Resend the animation event until the timeout is reached."""
        t = (datetime.datetime.now() - self.startTime).total_seconds()

        if t >= self.seconds or self._final_event:
            self.callback(1.0)
            self._result = msg
            self.remove()
            stop = StopIteration()
            stop.value = msg
            raise stop
        else:
            self.callback(t / self.seconds)
            t = (datetime.datetime.now() - self.startTime).total_seconds() # Recompute t after callback

            # Reraise event
            if self.seconds - t <= self.interval:
                self._final_event = True
                _THREAD_LOCALS._current_eventloop.postevent(Event(self, self, None), delay=max(0, self.seconds - t))
            else:
                _THREAD_LOCALS._current_eventloop.postevent(Event(self, self, None), delay=self.interval)


class Frame(Awaitable):
    """An object within the frame hierarchy.

    This class can be used in 2 ways:
    1) Annotate a coroutine with `@Frame` to use it in the frame hierarchy.
    2) Create a frame class by subclassing `Frame` and instantiate the frame class by annotating a coroutine with `@MyFrameClass`.
    """

    def __new__(cls, *frameclassargs, **frameclasskwargs):
        def ___new__(framefunc):
            def create_frame(*frameargs, **framekwargs):
                if _THREAD_LOCALS._current_eventloop is None:
                    raise InvalidOperationException("Can't call frame without a running event loop")
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

    def __init__(self, startup_behaviour=FrameStartupBehaviour.delayed):
        super().__init__(self.__class__.__name__)
        self.startup_behaviour = startup_behaviour
        self._parent = _THREAD_LOCALS._current_frame
        if self._parent:
            self._parent._children.append(self)
        self._children = []
        self._activechild = None
        self._primitives = []
        self._generator = None
        self.ready = EventSource(str(self.__name__) + ".ready", True)
        self.free = EventSource(str(self.__name__) + ".free", True)

    def create(self, framefunc, *frameargs, **framekwargs):
        """Start the frame function with the given arguments.

        Args:
            framefunc (function): A coroutine or regular function controlling the behaviour of this frame.
                                If `framefunc` is a coroutine, then the frame only exists until the coroutine exits.
        """

        if framefunc and not self.removed and self._generator is None:
            self.__name__ = framefunc.__name__
            self.free.__name__ = str(self.__name__) + ".free"

            # Activate self
            _THREAD_LOCALS._current_frame = self

            hasself = 'self' in inspect.signature(framefunc).parameters
            self._generator = framefunc(self, *frameargs, **framekwargs) if hasself else framefunc(*frameargs, **framekwargs)

            if inspect.isawaitable(self._generator): # If framefunc is a coroutine
                if self.startup_behaviour == FrameStartupBehaviour.delayed:
                    # Post coroutine to the event queue
                    _THREAD_LOCALS._current_eventloop._post(0.0, _THREAD_LOCALS._current_eventloop._start_coroutine, (self,))
                elif self.startup_behaviour == FrameStartupBehaviour.immediate:
                    # Start coroutine
                    try:
                        self.step(None, None)
                    except (StopIteration, GeneratorExit):
                        pass
                    finally:
                        # Activate parent
                        _THREAD_LOCALS._current_frame = self._parent

            # Activate parent
            _THREAD_LOCALS._current_frame = self._parent

    def step(self, sender, msg):
        """Resume the frame coroutine.

        Args:
            sender (Awaitable): The resumed awaitable
            msg (BaseException): A message to be forwarded to the coroutine or None to start the coroutine

        Raises:
            StopIteration: Raised if the coroutine finished with a result
            GeneratorExit: Raised if the coroutine finished without a result
            Exception: Raised if the coroutine encountered an error
        """

        if self.removed:
            stop = StopIteration()
            stop.value = self._result
            raise stop

        if self._generator is not None:
            try:
                awaitable = self._generator.send(msg) # Continue coroutine
            except StopIteration as stop: # If frame finished with result
                self._result = stop.value # Set frame result to stop.value
                if msg is None: self.ready.send(self) # Send ready event after coroutine ran once
                self.remove() # Remove finished frame
                raise # Propagate event
            except GeneratorExit: # If frame finished without result
                # Frame result stays None
                if msg is None: self.ready.send(self) # Send ready event after coroutine ran once
                self.remove() # Remove finished frame
                raise # Propagate event
            except Exception as err: # If frame raised exception
                # Frame result stays None
                self.remove() # Remove finished frame
                raise # Propagate event
            else: # If frame awaits awaitable
                awaitable._listeners.add(self) # Listen to events of awaitable
                if msg is None: self.ready.send(self) # Send ready event after coroutine ran once

    def remove(self):
        """Remove this awaitable from the frame hierarchy.

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        if self.removed:
            return False

        # Send frame free event
        _THREAD_LOCALS._current_eventloop.sendevent(Event(self, self.free, None))

        if self.removed: # If this frame was closed in response to the free event, ...
            return False

        # Remove child frames
        genexit = None
        while self._children:
            try:
                self._children[-1].remove()
            except GeneratorExit as err:
                genexit = err # Delay raising GeneratorExit

        # Remove self from parent frame
        if self._parent:
            self._parent._children.remove(self)

        # Remove primitives
        while self._primitives:
            self._primitives[-1].remove()

        # Stop framefunc
        if self._generator: # If framefunc is a coroutine
            if self._generator.cr_running:
                # Calling coroutine.close() from within the coroutine is illegal, so we throw a GeneratorExit manually instead
                self._generator = None
                genexit = GeneratorExit
            else:
                self._generator.close()
                self._generator = None

        # Post frame removed event
        _THREAD_LOCALS._current_eventloop.postevent(Event(self, self, None))

        # Remove awaitable
        super().remove()

        # Raise delayed GeneratorExit exception
        if genexit:
            raise genexit

        return True


class Primitive(object):
    """An object owned by a frame of the specified frame class.

    A primitive has to be created within the frame function of its owner or within the frame function of any child frame of its owning frame class.
    If it is created within a child frame, it will still be registered with the closest parent of the owning frame class.

    Args:
        owner (class): The owning frame class

    Raises:
        TypeError: Raised if owner is not a frame class
        Exception: Raised if a primitive is created outside the frame function of its owning frame class
    """

    def __init__(self, owner):
        self._removed = False

        # Validate parameters
        if not issubclass(owner, Frame):
            raise TypeError("'owner' must be of type Frame")

        # Find parent frame of class 'owner'
        self._owner = _THREAD_LOCALS._current_frame
        while self._owner and not issubclass(type(self._owner), owner):
            self._owner = self._owner._parent
        if not self._owner:
            raise InvalidOperationException(self.__class__.__name__ + " can't be defined outside " + owner.__name__)

        # Register with parent frame
        self._owner._primitives.append(self)

    def remove(self):
        """Remove this primitive from its owner.

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        if self._removed:
            return False
        self._removed = True
        self._owner._primitives.remove(self)
        return True
