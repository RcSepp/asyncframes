# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import abc
import collections
import collections.abc
import datetime
import enum
import inspect
import logging
import sys
import threading
import os
import queue
import warnings


__all__ = [
    'all_', 'animate', 'any_', 'Awaitable', 'AbstractEventLoop', 'Event',
    'find_parent', 'Frame', 'FrameStartupBehaviour', 'FreeEventArgs',
    'get_current_eventloop_index', 'InvalidOperationException', 'hold',
    'PFrame', 'Primitive', 'sleep'
]
__version__ = '2.0.0'


class ThreadLocals(threading.local):
    def __init__(self):
        self.__dict__['_current_eventloop'] = None
        self.__dict__['_current_frame'] = None
_THREAD_LOCALS = ThreadLocals()

class FrameStartupBehaviour(enum.Enum):
    delayed = 1
    immediate = 2

class InvalidOperationException(Exception):
    """Raised when operations are performed out of context.

    Args:
        msg (str): Human readable string describing the exception.
    """

    def __init__(self, msg):
        super().__init__(msg)

class FreeEventArgs(object):
    def __init__(self):
        self.cancel = False

class _AtomicCounter(object):
    """A thread-safe counter that calls a function whenever it hits zero.

        Args:
            initial_value (int): The initial counter value.
            on_zero (Callable): The function to call whenever the counter hits zero.
        """

    def __init__(self, initial_value, on_zero):
        self._lock = threading.Lock()
        self._value = initial_value
        self.on_zero = on_zero
        self.on_zero_args = ()

    def add(self, f):
        """Increment the counter by the given amount."""

        with self._lock:
            self._value += f
            if self._value != 0: return
        self.on_zero(*self.on_zero_args)

    def sub(self, f):
        """Decrement the counter by the given amount."""

        with self._lock:
            self._value -= f
            if self._value != 0: return
        self.on_zero(*self.on_zero_args)

class AbstractEventLoop(metaclass=abc.ABCMeta):
    """Abstract base class of event loops."""

    @abc.abstractmethod
    def _run(self):
        """Start the newly created or stopped event loop.

        This method must be overwritten by the concrete eventloop class.

        Events can be posted or invoked before the eventloop is started.
        """

        raise NotImplementedError # pragma: no cover

    @abc.abstractmethod
    def _stop(self):
        """Stop the running event loop.

        This method must be overwritten by the concrete eventloop class.
        """

        raise NotImplementedError # pragma: no cover

    @abc.abstractmethod
    def _close(self):
        """Close the stopped event loop.

        This method must be overwritten by the concrete eventloop class.

        The eventloop will not be restarted and no events will be posted or invoked after this method is called.
        """

        raise NotImplementedError # pragma: no cover

    @abc.abstractmethod
    def _clear(self):
        """Clear all pending events from the stopped event loop.

        This method must be overwritten by the concrete eventloop class.
        """

        raise NotImplementedError # pragma: no cover

    @abc.abstractmethod
    def _post(self, delay, callback, args):
        """Execute the given callback after ``delay`` seconds.

        This method must be overwritten by the concrete eventloop class.

        This function is **not** threadsafe. It is only called from the thread that this eventloop was started on.
        See :meth:`AbstractEventLoop._invoke` for the threadsafe version of this method.

        Args:
            delay (float): The time to wait before executing the callback.
            callback (function): The function to be called.
            args (tuple): The arguments to pass to the callback.
        """

        raise NotImplementedError # pragma: no cover

    @abc.abstractmethod
    def _invoke(self, delay, callback, args):
        """Execute the given callback after ``delay`` seconds.

        This method must be overwritten by the concrete eventloop class.

        This function **is** threadsafe. It can be called from any thread.
        See :meth:`AbstractEventLoop._post` for the unsafe version of this method.

        Args:
            delay (float): The time to wait before executing the callback.
            callback (function): The function to be called.
            args (tuple): The arguments to pass to the callback.
        """

        raise NotImplementedError # pragma: no cover

    def _spawnthread(self, target, args):
        """Create and start a daemonic worker thread.

        By default, this will create and start a ``threading.Thread``.
        The concrete eventloop class can overwrite this method to use a different threading model.

        Args:
            target (function): Same as the ``target`` argument of ``threading.Thread``.
            args (tuple): Same as the ``args`` argument of ``threading.Thread``.

        Returns:
            The created thread.
        """

        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
        return thread

    def _jointhread(self, thread):
        """Wait until the given thread terminates.

        Only threads created with :meth:`AbstractEventLoop._spawnthread` are awaited with this method.

        Args:
            thread: The thread to wait for.
        """

        thread.join()

    def __init__(self):
        self._idle = True
        self._eventloop_affinity = self
        self._result = None
        self._exception = None

    def run(self, frame, *frameargs, num_threads=0, **framekwargs):
        if num_threads <= 0:
            num_threads = len(os.sched_getaffinity(0))
        if _THREAD_LOCALS._current_eventloop is not None:
            raise InvalidOperationException("Another event loop is already running")
        _THREAD_LOCALS._current_eventloop = self

        eventloop_queue = queue.Queue()
        self.event_queue = queue.Queue()
        def worker_thread(parent_eventloop):
            eventloop = parent_eventloop.__class__()
            eventloop.event_queue = parent_eventloop.event_queue
            _THREAD_LOCALS._current_eventloop = eventloop
            eventloop_queue.put(eventloop)
            eventloop._run()
            eventloop._close()
        workers = [self._spawnthread(target=worker_thread, args=(self,)) for i in range(num_threads - 1)]

        # Collect an array of all eventloops and distribute that array among all eventloops
        self.eventloops = [self]
        for worker in workers: self.eventloops.append(eventloop_queue.get())
        for eventloop in self.eventloops[1:]: eventloop.eventloops = self.eventloops

        self._idle = False
        self._result = None
        self._exception = None

        try:
            mainframe = frame(*frameargs, **framekwargs)
            if not mainframe.removed:
                mainframe._listeners.add(self) # Listen to mainframe finished event
                self._run()
        except:
            raise
        else:
            if self._exception:
                raise self._exception
            else:
                return self._result
        finally:
            _THREAD_LOCALS._current_eventloop = None
            _THREAD_LOCALS._current_frame = None

            # Clear event queue
            while True:
                try:
                    self.event_queue.get(False)
                except queue.Empty:
                    break

            # Clear main eventloop
            self._clear()
            self._idle = True

            # Stop worker eventloops
            for eventloop in self.eventloops[1:]: eventloop._invoke(0, eventloop._stop, ())
            for worker in workers: self._jointhread(worker)

    def _enqueue(self, delay, callback, args, eventloop_affinity=None):
        if len(self.eventloops) == 1: # If running singlethreaded, ...
            # Execute callback from current eventloop
            if _THREAD_LOCALS._current_eventloop == self:
                self._post(delay, callback, args)
            else:
                self._invoke(delay, callback, args)
        elif eventloop_affinity: # If a target eventloop was provided, ...
            # Execute callback from target eventloop
            if _THREAD_LOCALS._current_eventloop == eventloop_affinity:
                eventloop_affinity._post(delay, callback, args)
            else:
                eventloop_affinity._invoke(delay, callback, args)
        else: # If no target eventloop was provided, ...
            if delay > 0.0:
                # Call _enqueue again with 0 delay after 'delay' seconds
                #TODO: Consider running a dedicated event loop instead of eventloops[-1] for delays
                if _THREAD_LOCALS._current_eventloop == self.eventloops[-1]:
                    self.eventloops[-1]._post(delay, self.eventloops[-1]._enqueue, (0.0, callback, args))
                else:
                    self.eventloops[-1]._invoke(delay, self.eventloops[-1]._enqueue, (0.0, callback, args))
            else: # If delay == 0, ...
                # Place the callback on the event queue
                self.event_queue.put((callback, args))

                # Wake up an idle event (if any)
                for eventloop in self.eventloops:
                    if eventloop._idle:
                        eventloop._idle = False
                        eventloop._invoke(0, eventloop._dequeue, ())
                        break

    def _dequeue(self):
        try:
            callback, args = self.event_queue.get_nowait()
        except queue.Empty:
            self._idle = True
        else:
            callback(*args)
            if not self.event_queue.empty():
                self._post(0, self._dequeue, ())
            else:
                self._idle = True

    @staticmethod
    def sendevent(eventsource, event, process_counter=None, blocking=False):
        # Save current frame, since it will be modified inside Awaitable.process()
        currentframe = _THREAD_LOCALS._current_frame

        try:
            eventsource.process(eventsource, event, process_counter, blocking)
        finally:
            # Restore current frame
            _THREAD_LOCALS._current_frame = currentframe

    def postevent(self, eventsource, event, delay=0):
        self._enqueue(delay, AbstractEventLoop.sendevent, (eventsource, event, None, False), eventsource._eventloop_affinity)

    def process(self, sender, msg, process_counter=None, blocking=False):
        self._result = msg
        self._stop() # Stop event loop


class Awaitable(collections.abc.Awaitable):
    """An awaitable frame or event.

    Every node in the frame hierarchy is a subclass of `Awaitable`. An awaitable has a `__name__`,
    a parent awaitable (None, if the awaitable is the main frame), a list of child awaitables and
    a result, that gets set when the awaitable finishes.

    Args:
        name (str): The name of the awaitable.
    """

    def __init__(self, name):
        self.__name__ = name
        self._parent = None
        self._removed = False
        self._result = None
        self._listeners = set()
        self._eventloop_affinity = None
        self.exception_handler = None

    def _remove(self, process_counter=None, blocking=False, ondone=lambda result: None):
        # Mark self as removed
        if self._removed:
            ondone(False)
            if process_counter:
                process_counter.sub(1)
            return
        self._removed = True

        # Remove self from parent frame
        if self._parent:
            self._parent._children.remove(self)

        # Wake up listeners
        if self._listeners:
            listeners = self._listeners
            self._listeners = set()

            if blocking:
                if process_counter:
                    process_counter.add(len(listeners))

                for listener in listeners:
                    if listener._eventloop_affinity is None or listener._eventloop_affinity == _THREAD_LOCALS._current_eventloop:
                        listener.process(self, self._result, process_counter, blocking)
                    else:
                        listener._eventloop_affinity._invoke(0, listener.process, (self, self._result, process_counter, blocking))
            else:
                for listener in listeners:
                    _THREAD_LOCALS._current_eventloop._enqueue(0, listener.process, (self, self._result), listener._eventloop_affinity)

        del self
        ondone(True)
        if process_counter:
            process_counter.sub(1)
        return

    def remove(self):
        """Remove this awaitable from the frame hierarchy.

        Returns:
            bool: If `True`, this event was removed. If `False` the request was either canceled, or the event had already been removed before
        """

        remove_event = Event(str(self.__name__) + ".remove", singleshot=True)
        process_counter = _AtomicCounter(1, lambda result: AbstractEventLoop.sendevent(remove_event, result, None, True)) # Add process: Frame.remove
        process_counter.on_zero_args = (True,) # Default remove() result to True
        def onremoved(result):
            process_counter.on_zero_args = (result,)
        self._remove(process_counter, False, onremoved)
        return remove_event

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
            return (yield self)
        except (StopIteration, GeneratorExit):
            return self._result

    @abc.abstractmethod
    def _step(self, sender, msg):
        raise NotImplementedError # pragma: no cover

    def process(self, sender, msg, process_counter=None, blocking=False):
        """Propagate an event from its source and along awaiting nodes through the frame hierarchy.

        Args:
            sender (Awaitable): The source of the event or an awaited node that woke up.
            msg: The incomming event or propagated message.
        """

        _THREAD_LOCALS._current_frame = self # Activate self
        try:
            self._step(sender, msg)
        except BaseException as err:
            if getattr(self, 'ready', True): # If self is ready or self doesn't have a ready event
                # Send ready event to all listeners that have a ready event, but aren't ready yet
                for listener in self._listeners:
                    if not getattr(listener, 'ready', True):
                        AbstractEventLoop.sendevent(listener.ready, None, None, True)

            # Store result
            if type(err) == StopIteration:
                self._result = err.value
            elif type(err) != GeneratorExit:
                self._result = err

                # Call exception handler
                if err != msg:
                    awaitable = self
                    while awaitable:
                        if awaitable.exception_handler:
                            try:
                                awaitable.exception_handler(self, err)
                            except Exception as exception_handler_err:
                                err = exception_handler_err
                            else:
                                break
                        awaitable = awaitable._parent
                    if not awaitable:
                        maineventloop = _THREAD_LOCALS._current_eventloop.eventloops[0]
                        maineventloop._exception = err
                        if maineventloop._eventloop_affinity is None or maineventloop._eventloop_affinity == _THREAD_LOCALS._current_eventloop:
                            maineventloop._stop()
                        else:
                            maineventloop._eventloop_affinity._invoke(0, maineventloop._stop, ())

            # Remove awaitable and propagate event
            self._remove(process_counter, blocking)
        else:
            if getattr(self, 'ready', True): # If self is ready or self doesn't have a ready event
                # Send ready event to all listeners that have a ready event, but aren't ready yet
                for listener in self._listeners:
                    if not getattr(listener, 'ready', True):
                        AbstractEventLoop.sendevent(listener.ready, None, None, True)

            if process_counter:
                process_counter.sub(1)

    def __and__(self, other):
        """Register A & B as shortcut for ``all_(A, B)``.

        Args:
            other (Awaitable): The other awaitable.

        Returns:
            all\_: A frame awaiting `self` and `other`.
        """

        return all_(self, other)
    def __or__(self, other):
        """Register A | B as shortcut for ``any_(A, B)``.

        Args:
            other (Awaitable): The other awaitable.

        Returns:
            any\_: A frame awaiting `self` or `other`.
        """

        return any_(self, other)

class Event(Awaitable):
    """An awaitable event.

    Instantiate or overload this class to implement new events.
    Each type of event should be emitted by exactly one event class.
    For example, key-up and key-down events should be implemented by two separate events.
    Events represent leave nodes in the frame hierarchy.

    Args:
        name (str): The name of the event.
        singleshot (bool, optional): Defaults to False. If `True`, removes the event after it has been woken.
    """

    def __init__(self, name, singleshot=False):
        super().__init__(name)
        self.singleshot = singleshot
        self.eventloop = _THREAD_LOCALS._current_eventloop # Store creating eventloop, as a fallback in case self.post() is called from a thread without an eventloop

    def _remove(self, process_counter=None, blocking=False, ondone=lambda result: None):
        if self.singleshot:
            super()._remove(process_counter, blocking, ondone)
        else:
            # Wake up listeners
            if self._listeners:
                listeners = self._listeners
                self._listeners = set()

                if blocking:
                    if process_counter is not None:
                        process_counter.add(len(listeners))

                    for listener in listeners:
                        if listener._eventloop_affinity is None or listener._eventloop_affinity == _THREAD_LOCALS._current_eventloop:
                            listener.process(self, self._result, process_counter, blocking)
                        else:
                            listener._eventloop_affinity._invoke(0, listener.process, (self, self._result, process_counter, blocking))
                else:
                    for listener in listeners:
                        _THREAD_LOCALS._current_eventloop._enqueue(0, listener.process, (self, self._result), listener._eventloop_affinity)
            ondone(False)
            if process_counter:
                process_counter.sub(1)

    def __bool__(self):
        return self._removed

    def _step(self, sender, msg):
        """Handle incoming events.

        Args:
            sender (Event): The event to be handled. This value is always identical to `self`.
            msg: The event arguments.

        Raises:
            StopIteration: If this event should wake up awaiting frames, raise a StopIteration with `value` set to the event arguments.
        """

        stop = StopIteration()
        stop.value = msg
        raise stop

    def send(self, args=None):
        """Dispatch and immediately process an event.

        Args:
            args (optional): Defaults to None. Event arguments, for example, the progress value on a progress-update event.
        """

        send_event = Event(str(self.__name__) + ".send", singleshot=True)
        process_counter = _AtomicCounter(1, lambda: AbstractEventLoop.sendevent(send_event, None, None, True))
        AbstractEventLoop.sendevent(self, args, process_counter, True)
        return send_event

    def post(self, args=None, delay=0):
        """Enqueue an event in the event loop.

        Args:
            args (optional): Defaults to None. Event arguments, for example, the progress value on a progress-update event.
            delay (float, optional): Defaults to 0. The time in seconds to wait before posting the event.
        """

        (_THREAD_LOCALS._current_eventloop or self.eventloop).postevent(self, args, delay)

class all_(Awaitable):
    """An awaitable that blocks the awaiting frame until all passed awaitables have woken up.

    Args:
        awaitables (Awaitable[]): A list of all awaitables to await.
    """

    def __init__(self, *awaitables):
        super().__init__("all({})".format(", ".join(str(a) for a in awaitables)))
        self._remove_lock = threading.Lock()

        self._awaitables = collections.defaultdict(list)
        self._result = [None] * len(awaitables)
        for i, awaitable in enumerate(awaitables):
            if awaitable.removed:
                self._result[i] = awaitable._result
            else:
                self._awaitables[awaitable].append(i)
                awaitable._listeners.add(self)

        if not self._awaitables:
            self._remove()
            return

        self._parent = _THREAD_LOCALS._current_frame
        if self._parent:
            self._parent._children.append(self)

    def _step(self, sender, msg):
        """Respond to an awaking child.

        Args:
            sender (Awaitable): The awaking child.
            msg: The awaking child's result or an exception raised in a child frame.

        Raises:
            StopIteration: Once all children woke up, this raises a StopIteration with `value` set to a dict of all children's results.
            BaseException: If msg is an Exception other than GeneratorExit or StopIteration, the exception is re-raised.
        """

        for i in self._awaitables.pop(sender, ()):
            self._result[i] = msg

        if not self._awaitables:
            stop = StopIteration()
            stop.value = self._result
            raise stop

    def _remove(self, process_counter=None, blocking=False, ondone=lambda result: None):
        if self.removed:
            ondone(False)
            if process_counter:
                process_counter.sub(1)
            return

        with self._remove_lock:
            if self.removed: # If this frame was closed while acquiring the lock, ...
                ondone(False)
                if process_counter:
                    process_counter.sub(1)
                return

            for awaitable in self._awaitables:
                awaitable._listeners.discard(self)
            self._awaitables.clear()

            # Remove awaitable
            super()._remove(process_counter, blocking, ondone)
            return
        if process_counter:
            process_counter.sub(1)
        ondone(False)

class any_(Awaitable):
    """An awaitable that blocks the awaiting frame until any of the passed awaitables wakes up.

    Args:
        awaitables (Awaitable[]): A list of all awaitables to await.
    """

    def __init__(self, *awaitables):
        super().__init__("any({})".format(", ".join(str(a) for a in awaitables)))
        self._remove_lock = threading.Lock()

        self._awaitables = set()
        for awaitable in awaitables:
            if awaitable.removed:
                self._result = (awaitable, awaitable._result)
                self._remove()
                return
            else:
                self._awaitables.add(awaitable)
                awaitable._listeners.add(self)

        self._parent = _THREAD_LOCALS._current_frame
        if self._parent:
            self._parent._children.append(self)

    def _step(self, sender, msg):
        """Respond to an awaking child.

        Args:
            sender (Awaitable): The awaking child.
            msg: The awaking child's result or an exception raised in a child frame.

        Raises:
            StopIteration: If msg indicates an awaking child, store its result as this frame's result.
            BaseException: Forward any exceptions.
        """

        stop = StopIteration()
        stop.value = (sender, msg)
        raise stop

    def _remove(self, process_counter=None, blocking=False, ondone=lambda result: None):
        if self.removed:
            ondone(False)
            if process_counter:
                process_counter.sub(1)
            return

        with self._remove_lock:
            if self.removed: # If this frame was closed while acquiring the lock, ...
                ondone(False)
                if process_counter:
                    process_counter.sub(1)
                return

            for awaitable in self._awaitables:
                awaitable._listeners.discard(self)
            self._awaitables.clear()

            # Remove awaitable
            super()._remove(process_counter, blocking, ondone)
            return
        if process_counter:
            process_counter.sub(1)
        ondone(False)


class sleep(Event):
    """An awaitable event used for suspending execution by the specified amount of time.

    A duration of 0 seconds will resume the awaiting frame as soon as possible.
    This is useful to implement non-blocking loops.

    Args:
        seconds (float, optional): Defaults to 0. The duration to wait.
    """

    def __init__(self, seconds=0.0):
        super().__init__("sleep({})".format(seconds), singleshot=True)

        # Raise event
        self.post(None, max(0, seconds))

class hold(Event):
    """An awaitable event used for suspending execution indefinitely.

    Frames are automatically removed when the frame coroutine finishes.
    If you would like the frame to remain open until it is removed, write `await hold()` at the end of the coroutine.
    """

    def __init__(self):
        super().__init__("hold()", singleshot=True)
    def _step(self, sender, msg):
        """ Ignore any incoming events."""

        pass

class animate(Event):
    """An awaitable event used for periodically calling a callback function for the specified amount of time.

    Args:
        seconds (float): The duration of the animation.
        callback (Callable[float, None]): The function to be called on every iteration. The first parameter of `callback` indicates animation progress between 0 and 1.
        interval (float, optional): Defaults to 0.0. The minimum time in seconds between two consecutive calls of the callback.
    """

    def __init__(self, seconds, callback, interval=0.0):
        super().__init__("animate()", singleshot=True)
        self.seconds = seconds
        self.callback = callback
        self.interval = interval
        self.startTime = datetime.datetime.now()
        self._final_event = False

        # Raise event
        if seconds <= interval:
            self._final_event = True
            self.post(None, max(0, seconds))
        else:
            self.post(None, interval)

    def _step(self, sender, msg):
        """Resend the animation event until the timeout is reached."""
        t = (datetime.datetime.now() - self.startTime).total_seconds()

        if t >= self.seconds or self._final_event:
            self.callback(1.0)
            stop = StopIteration()
            stop.value = msg
            raise stop
        else:
            self.callback(t / self.seconds)
            t = (datetime.datetime.now() - self.startTime).total_seconds() # Recompute t after callback

            # Reraise event
            if self.seconds - t <= self.interval:
                self._final_event = True
                self.post(None, max(0, self.seconds - t))
            else:
                self.post(None, self.interval)

class FrameMeta(abc.ABCMeta):
    def __new__(mcs, name, bases, dct):
        frameclass = super().__new__(mcs, name, bases, dct)
        if bases != (Awaitable,): # If frameclass != Frame, ...
            frameclass.Factory = type(frameclass.__name__ + '.Factory', (frameclass.Factory,), {}) # Derive factory from base class factory
        frameclass.Factory.frameclass = frameclass
        return frameclass

class Frame(Awaitable, metaclass=FrameMeta):
    """An object within the frame hierarchy.

    This class represents the default frame class. All other frame classes have
    to be derived from :class:`Frame`.

    A frame is an instance of a frame class. Use the nested Factory class to
    create frames.

    The factory class is created by decorating a function or coroutine with
    ``@FRAME``, where ``FRAME`` is the frame class.

    Example: ::

        class MyFrameClass(Frame):
            pass

        @MyFrameClass
        async def my_frame_factory():
            pass

        assert(type(my_frame_factory) == MyFrameClass.Factory)
        my_frame = my_frame_factory()
        assert(type(my_frame) == MyFrameClass)

    Args:
        startup_behaviour (FrameStartupBehaviour, optional): Defaults to FrameStartupBehaviour.delayed.
            Controls whether the frame is started immediately or queued on the eventloop.
        thread_idx (int, optional): Defaults to None. If set, forces the scheduler to affiliate this frame with the given thread.

    Raises:
        ValueError: If `thread_idx` is outside the range of allocated threads.

            The number of allocated threads is controlled by the `num_threads` parameter of :meth:`AbstractEventLoop.run`.
    """

    class Factory(object):
        """A frame function declared in the context of a frame class.
        
        Args:
            framefunc (Callable): The function or coroutine that describes the frame's behaviour.
            frameclassargs (tuple): Positional arguments to the frame class.
            frameclasskwargs (dict): Keyword arguments to the frame class.
        """

        def __init__(self, framefunc, frameclassargs, frameclasskwargs):
            self.framefunc = framefunc
            self.frameclassargs = frameclassargs
            self.frameclasskwargs = frameclasskwargs

        def __call__(self, *frameargs, **framekwargs):
            """Produce an instance of the frame.
            
            Raises:
                InvalidOperationException: Raised when no event loop is currently running.
            
            Returns:
                Frame: The newly created frame instance.
            """

            if _THREAD_LOCALS._current_eventloop is None:
                raise InvalidOperationException("Can't call frame without a running event loop")
            frame = super(Frame, self.__class__.frameclass).__new__(self.__class__.frameclass)
            frame.__init__(*self.frameclassargs, **self.frameclasskwargs)
            frame.create(self.framefunc, *frameargs, **framekwargs)
            return frame

    def __new__(cls, *frameclassargs, **frameclasskwargs):
        if len(frameclassargs) == 1 and not frameclasskwargs and callable(frameclassargs[0]): # If @frame was called without parameters
            framefunc = frameclassargs[0]
            frameclassargs = ()
            return cls.Factory(framefunc, frameclassargs, frameclasskwargs)
        else: # If @frame was called with parameters
            return lambda framefunc: cls.Factory(framefunc, frameclassargs, frameclasskwargs)

    def __init__(self, startup_behaviour=FrameStartupBehaviour.delayed, thread_idx=None):
        if thread_idx is not None and (thread_idx < 0 or thread_idx >= len(_THREAD_LOCALS._current_eventloop.eventloops)):
            raise ValueError("thread_idx must be an index between 0 and " + str(len(_THREAD_LOCALS._current_eventloop.eventloops)))
        super().__init__(self.__class__.__name__)
        self.startup_behaviour = startup_behaviour
        self._parent = _THREAD_LOCALS._current_frame
        if self._parent:
            self._parent._children.append(self)
        self._children = []
        self._activechild = None
        self._primitives = []
        self._generator = None
        self._generator_eventloop = None
        self._freeing = False
        self.ready = Event(str(self.__name__) + ".ready", True)
        self.ready.ready = self.ready # Set ready state of ready event to itself. This way the ready event will propagate through `await frame.ready`
        self.free = Event(str(self.__name__) + ".free", False)
        self._eventloop_affinity = _THREAD_LOCALS._current_eventloop
        if thread_idx is not None:
            self._eventloop_affinity = self._eventloop_affinity.eventloops[thread_idx]
        self._remove_lock = threading.Lock()

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
                    _THREAD_LOCALS._current_eventloop.postevent(self, None, 0.0)
                elif self.startup_behaviour == FrameStartupBehaviour.immediate:
                    # Start coroutine
                    try:
                        self._step(None, None)
                    except (StopIteration, GeneratorExit):
                        pass
                    finally:
                        # Activate parent
                        _THREAD_LOCALS._current_frame = self._parent
                else:
                    raise ValueError('startup_behaviour must be FrameStartupBehaviour.delayed or FrameStartupBehaviour.immediate')

            # Activate parent
            _THREAD_LOCALS._current_frame = self._parent

    def _step(self, sender, msg):
        """Resume the frame coroutine.

        Args:
            sender (Awaitable): The resumed awaitable.
            msg: A message to be forwarded to the coroutine or None to start the coroutine.

        Raises:
            StopIteration: Raised if the coroutine finished with a result.
            GeneratorExit: Raised if the coroutine finished without a result.
            Exception: Raised if the coroutine encountered an error.
        """

        if self.removed:
            stop = StopIteration()
            stop.value = self._result
            raise stop

        if self._generator is not None:
            self._generator_eventloop = _THREAD_LOCALS._current_eventloop
            try:
                awaitable = self._generator.send(msg) # Continue coroutine
            except (StopIteration, GeneratorExit): # If frame finished
                self._generator_eventloop = None
                if msg is None: AbstractEventLoop.sendevent(self.ready, None, None, True) # Send ready event if frame finished without ever being awaited
                raise # Propagate event
            except Exception as err: # If frame raised exception
                self._generator_eventloop = None
                raise # Propagate event
            else: # If frame awaits awaitable
                self._generator_eventloop = None
                awaitable._listeners.add(self) # Listen to events of awaitable

                # Send ready event if not yet ready and awaitable is ready or doesn't have a ready event
                if getattr(awaitable, 'ready', True) and not self.ready: # If awaitable is ready or awaitable doesn't have a ready event
                    AbstractEventLoop.sendevent(self.ready, None, None, True)

    def _mark_freeing(self, value):
        self._freeing = value
        for child in self._children:
            if isinstance(child, Frame):
                child._mark_freeing(value)

    def _send_free_event(self, free_args, process_counter):
        process_counter.add(len(self._children))

        # Send child frame free events
        for child in self._children:
            if isinstance(child, Frame):
                child._send_free_event(free_args, process_counter)
            else:
                process_counter.sub(1)

        # Send current frame free event
        AbstractEventLoop.sendevent(self.free, free_args, process_counter, True)

    def _remove(self, process_counter=None, blocking=False, ondone=lambda result: None):
        if self._freeing: # If this frame's free event is being processed, ...
            self._remove_stage2(process_counter, blocking, ondone) # Remove the frame
        else: # If this frame's free event wasn't send yet, ...
            self._mark_freeing(True) # Mark this frame and all children for removal

            free_args = FreeEventArgs()
            def after_free():
                if free_args.cancel: # If the free event was canceled, ...
                    self._mark_freeing(False) # Unmark this frame and all children from removal
                    ondone(False) # Awake awaiting frames with value 'False'
                    if process_counter:
                        process_counter.sub(1)
                elif self._removed: # If this frame was removed as a result of the free event, ...
                    ondone(True) # Awake awaiting frames with value 'True'
                    if process_counter:
                        process_counter.sub(1)
                else: # If the free event wasn't canceled and didn't remove this frame, ...
                    self._remove_stage2(process_counter, blocking, ondone) # Remove this frame
            self._send_free_event(free_args, _AtomicCounter(1, after_free))

    def _remove_stage2(self, process_counter=None, blocking=False, ondone=lambda result: None):
        if self.removed or not self._remove_lock.acquire(blocking=False): # If this frame was closed in response to the free event or removal is already in progress, ...
            ondone(False)
            if process_counter:
                process_counter.sub(1) # Remove process: Frame._remove_stage2
        else:
            try:
                # Remove child frames
                genexit = None
                if process_counter:
                    process_counter.add(len(self._children))
                while self._children:
                    try:
                        self._children[-1]._remove(process_counter, blocking)
                    except GeneratorExit as err:
                        genexit = err # Delay raising GeneratorExit

                # Remove primitives
                while self._primitives:
                    self._primitives[-1].remove()

                # Stop framefunc
                if self._generator: # If framefunc is a coroutine
                    genevtlp = self._generator_eventloop # Avoid race condition between if and invoke
                    if genevtlp == _THREAD_LOCALS._current_eventloop: # If the coroutine is running on the current eventloop
                        # Calling coroutine.close() from within the coroutine is illegal, so we throw a GeneratorExit manually instead
                        try:
                            self._generator.close()
                        except ValueError:
                            genexit = GeneratorExit()
                        self._generator = None
                    elif genevtlp is not None: # If the coroutine is running on another eventloop
                        if process_counter:
                            process_counter.add(1) # Add process: Frame._remove_stage3
                        genevtlp._invoke(0, self._remove_stage3, (process_counter,))
                    else: # If the coroutine isn't running
                        self._generator.close()
                        self._generator = None

                # Remove awaitable
                super()._remove(process_counter, blocking, ondone)
            finally:
                self._remove_lock.release()

                # Raise delayed GeneratorExit exception
                if genexit:
                    raise genexit

    def _remove_stage3(self, process_counter=None):
        genevtlp = self._generator_eventloop # Avoid race condition between if and invoke
        if genevtlp is None or genevtlp == _THREAD_LOCALS._current_eventloop: # If the coroutine isn't running or it's running on the current eventloop
            self._generator.close()
            if process_counter:
                process_counter.sub(1) # Remove process: Frame._remove_stage3
        else: # If the coroutine is running on another eventloop
            genevtlp._invoke(0, self._remove_stage3, (process_counter,))

class PFrame(Frame):
    """A parallel :class:`Frame` that can run on any thread.

    Multithreading can be enabled for any frame by changing its base class to
    :class:`PFrame`.

    The only difference between :class:`Frame` and :class:`PFrame` is that
    instances of :class:`PFrame` are not restricted to run on the same thread as
    their parent frame.

    Args:
        startup_behaviour (FrameStartupBehaviour, optional): Defaults to FrameStartupBehaviour.delayed.
            Controls whether the frame is started immediately or queued on the eventloop.
        thread_idx (int, optional): Defaults to None. If set, forces the scheduler to affiliate this frame with the given thread.

    Raises:
        ValueError: If `thread_idx` is outside the range of allocated threads.

            The number of allocated threads is controlled by the `num_threads` parameter of :meth:`AbstractEventLoop.run`.
    """

    def __init__(self, startup_behaviour=FrameStartupBehaviour.delayed, thread_idx=None):
        super().__init__(startup_behaviour, thread_idx)
        if thread_idx is None:
            self._eventloop_affinity = None


class Primitive(object):
    """An object owned by a frame of the specified frame class.

    A primitive has to be created within the frame function of its owner or within the frame function of any child frame of its owning frame class.
    If it is created within a child frame, it will still be registered with the closest parent of the owning frame class.

    Args:
        owner (class): The owning frame class.

    Raises:
        TypeError: Raised if owner is not a frame class.
        Exception: Raised if a primitive is created outside the frame function of its owning frame class.
    """

    def __init__(self, owner):
        self._removed = False

        # Validate parameters
        if not issubclass(owner, Frame):
            raise TypeError("'owner' must be of type Frame")

        # Find parent frame of class 'owner'
        self._owner = find_parent(owner)
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


def get_current_eventloop_index():
    return _THREAD_LOCALS._current_eventloop.eventloops.index(_THREAD_LOCALS._current_eventloop) if getattr(_THREAD_LOCALS, '_current_eventloop', None) and hasattr(_THREAD_LOCALS._current_eventloop, 'eventloops') else None

def find_parent(parenttype):
    parent = _THREAD_LOCALS._current_frame
    while parent and not issubclass(type(parent), parenttype):
        parent = parent._parent
    return parent
