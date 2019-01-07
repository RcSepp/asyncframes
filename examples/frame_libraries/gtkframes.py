# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from functools import partial
from asyncframes import Frame, FrameMeta, Primitive, Event, find_parent
from gi.repository import Gtk, GObject

__all__ = ['Container', 'Window', 'ScrolledWindow', 'Box', 'Button', 'Image']

class GtkFrame(FrameMeta, type(GObject.GObject)):
    pass

def _connect_events(obj, cls):
    for signal_name in GObject.signal_list_names(cls):
        signal_name = signal_name.replace('-', '_')
        event = Event(obj.__class__.__name__ + '.' + signal_name)
        setattr(obj, signal_name, event)
        def send_event(event, *args):
            event.send(args)
        obj.connect(signal_name, partial(send_event, event))

class Container(Frame):
    def __init__(self):
        super().__init__()
    def add(self, widget):
        raise NotImplementedError

class Window(Container, Gtk.Window, metaclass=GtkFrame):
    def __init__(self, *args, **kwargs):
        Frame.__init__(self)
        Gtk.Window.__init__(self, *args, **kwargs)
        self.connect("destroy", lambda _: self.remove())
        _connect_events(self, Gtk.Widget)
        _connect_events(self, Gtk.Window)
    def add(self, widget):
        Gtk.Window.add(self, widget)

class ScrolledWindow(Container, Gtk.ScrolledWindow, metaclass=GtkFrame):
    def __init__(self, *args, **kwargs):
        Frame.__init__(self)
        Gtk.ScrolledWindow.__init__(self, *args, **kwargs)
        parent = find_parent(Container)
        if not parent:
            raise Exception("ScrolledWindow needs to be defined inside a Window")
        parent.add(self)
        _connect_events(self, Gtk.Widget)
        _connect_events(self, Gtk.ScrolledWindow)
    def add(self, widget):
        Gtk.ScrolledWindow.add(self, widget)

class Box(Container, Gtk.Box, metaclass=GtkFrame):
    def __init__(self, *args, **kwargs):
        Frame.__init__(self)
        Gtk.Box.__init__(self, *args, **kwargs)
        parent = find_parent(Container)
        if not parent:
            raise Exception("Box needs to be defined inside a Window")
        parent.add(self)
        _connect_events(self, Gtk.Widget)
        _connect_events(self, Gtk.Box)
    def add(self, widget):
        self.pack_start(widget, True, True, 0)

class Button(Primitive, Gtk.Button):
    def __init__(self, *args, **kwargs):
        Primitive.__init__(self, Container)
        Gtk.Button.__init__(self, *args, **kwargs)
        self._owner.add(self)
        _connect_events(self, Gtk.Widget)
        _connect_events(self, Gtk.Button)

class Image(Primitive, Gtk.Image):
    def __init__(self, *args, **kwargs):
        Primitive.__init__(self, Container)
        Gtk.Image.__init__(self, *args, **kwargs)
        self._owner.add(self)
        _connect_events(self, Gtk.Widget)
        _connect_events(self, Gtk.Image)
