Changelog
=========

2.1.0 (2019-01-07)
------------------

- GTK support - Create GTK widgets using the GLib eventloop.

2.0.0 (2018-12-06)
------------------

- Multithreading - Run frames in parallel using PFrame's.
- Delayed startup - By default creating a frame queues it's execution and returns immediately.
- Frame exception handlers - Exceptions propagate along the frame hierarchy, instead of along awaiting frames.
- Simplified events - EventSource's are now Event's. Awaited events emit only event arguments.
- Cancelable free events - Cancel free events by setting event.cancel to True.
- Frame factories - Instances of frame classes are of type [MyFrameClass].Factory.
- Threadsafe post() - Use post() to queue events on any thread, instead of separate post & invoke functions.
- "singleshot" - Event argument "autoremove" has been renamed to "singleshot"

1.1.0 (2018-09-18)
------------------

- Threadsafe events - Wake up event sources across threads using invoke().
- Free event - Frames emit the self.free event just before they are removed.
- Hierarchy changes - any\_ and all\_ do not take over parenthood of their awaitables.


1.0.0 (2018-09-05)
------------------

- Initial release