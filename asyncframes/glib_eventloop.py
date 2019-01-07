# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
import asyncframes


class EventLoop(asyncframes.AbstractEventLoop):
    """An implementation of AbstractEventLoop based on GLib."""

    def __init__(self):
        super().__init__()
        if isinstance(threading.current_thread(), threading._MainThread):
            self._context = GLib.main_context_default()
        else:
            self._context = GLib.MainContext()
        self.loop = GLib.MainLoop(self._context)
        self.pending_events = set()

    def _run(self):
        self.loop.run()

    def _stop(self):
        self.loop.quit()

    def _close(self):
        pass

    def _clear(self):
        for event in self.pending_events:
            event.destroy()
        self.pending_events.clear()

    def _post(self, delay, callback, args):
        event = GLib.Timeout(delay * 1000) if delay > 0 else GLib.Idle()
        self.pending_events.add(event)
        def fire(context):
            self.pending_events.remove(event)
            event.destroy()
            callback(*args)
        event.set_callback(fire, None)
        event.attach(self._context)

    def _invoke(self, delay, callback, args):
        event = GLib.Timeout(delay * 1000) if delay > 0 else GLib.Idle()
        self.pending_events.add(event)
        def fire(context):
            self.pending_events.remove(event)
            event.destroy()
            callback(*args)
        event.set_callback(fire, None)
        event.attach(self._context)
