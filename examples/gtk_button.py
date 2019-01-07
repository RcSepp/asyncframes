# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

from asyncframes import Event, Frame, FrameMeta, hold, find_parent, glib_eventloop
from gi.repository import Gtk
from gi.repository.GObject import GObject

class GtkFrame(FrameMeta, type(GObject)):
    pass

class Window(Frame, Gtk.Window, metaclass=GtkFrame):
    def __init__(self, *args, **kwargs):
        Frame.__init__(self)
        Gtk.Window.__init__(self, *args, **kwargs)
        self.connect("destroy", lambda _: self.remove())

class Button(Frame, Gtk.Button, metaclass=GtkFrame):
    def __init__(self, *args, **kwargs):
        Frame.__init__(self)
        Gtk.Button.__init__(self, *args, **kwargs)
        find_parent(Window).add(self)

        self.clicked = Event("Button.clicked")
        def send_clicked_event(*args):
            self.clicked.send(args)
        self.connect("clicked", send_clicked_event)

@Window(title="Button Example")
async def main_frame(self):
    @Button("Click Here")
    async def button_frame(self):
        self.show()
        while True:
            await self.clicked
            print("Hello World!")
    button = button_frame()

    self.set_default_size(280, 40)
    self.set_border_width(8)
    self.show()
    await hold()

loop = glib_eventloop.EventLoop()
loop.run(main_frame)
