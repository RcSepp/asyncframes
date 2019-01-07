# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import os
import os.path
import re
import sys
from asyncframes import Frame, Event, hold, sleep
from asyncframes.glib_eventloop import EventLoop
from gi.repository import Gtk, GObject, GdkPixbuf
from frame_libraries.gtkframes import *

@Window(title="Image Viewer")
async def main_frame(self):
    # Create scrollable image viewer
    @ScrolledWindow
    async def scroll_frame(self):
        self.image = Image()
    image_viewer = scroll_frame()
    await image_viewer.ready

    self.set_default_size(800, 600)
    self.show_all()

    @Frame
    async def input_listener_frame(self, target):
        self.key_left = Event("key_left")
        self.key_right = Event("key_right")
        events_by_keycode = {
            0xFF51: self.key_left,
            0xFF53: self.key_right
        }

        while True:
            try:
                keycode = (await target.key_press_event)[1].keyval
                events_by_keycode[keycode].post()
            except KeyError:
                pass
    input_listener = input_listener_frame(self)
    await input_listener.ready

    image_loader = image_loader_frame(sys.argv[1] if len(sys.argv) > 1 else '.', input_listener.key_right, input_listener.key_left)
    await image_loader.ready

    # print(sys.argv)

    pixbuf = await image_loader.image_loaded
    while True:
        image_sizer = image_sizer_frame(image_viewer, pixbuf)
        pixbuf = await image_loader.image_loaded
        await image_sizer.remove()


@Frame
async def image_loader_frame(self, path, next_image_event, prev_image_event):
    self.image_loaded = Event("image_loader.image_loaded")

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    IMAGE_FILE_REGEX = re.compile(r".*\.(?:(?:jpg)|(?:png))", re.IGNORECASE)
    if os.path.isdir(path):
        image_paths = [os.path.join(path, file) for file in os.listdir(path) if IMAGE_FILE_REGEX.match(file)]
        image_index = 0
        print([os.path.join(path, file) for file in os.listdir(path)])
    else:
        imagedir = os.path.split(path)[0]
        image_paths = [os.path.join(imagedir, file) for file in os.listdir(imagedir) if IMAGE_FILE_REGEX.match(file)]
        image_index = image_paths.index(path)

    if not image_paths:
        return

    while True:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(image_paths[image_index])
        self.image_loaded.post(pixbuf)
        event = (await (next_image_event | prev_image_event))[0]
        image_index = (image_index + (1 if event is next_image_event else -1)) % len(image_paths)

@Frame
async def image_sizer_frame(image_viewer, pixbuf):
    image_size = (pixbuf.get_width(), pixbuf.get_height())
    scroll_level = 0
    visible_rect = image_viewer.get_allocated_size().allocation

    while True:
        image_scale = 10 ** (0.1 * scroll_level)
        target_size = fit_image(image_size, (visible_rect.width, visible_rect.height), image_scale)
        image_viewer.image.set_from_pixbuf(pixbuf.scale_simple(*target_size, 3))

        event, args = await (image_viewer.size_allocate | image_viewer.scroll_event)
        if event == image_viewer.size_allocate:
            visible_rect = args[1]
        elif event == image_viewer.scroll_event:
            scroll = args[1]
            scroll_level = max(0, scroll_level - scroll.get_scroll_deltas()[2])

def fit_image(original_size, viewer_size, image_scale):
    # scaled_size = original_size * image_scale
    scaled_size = (original_size[0] * image_scale, original_size[1] * image_scale)

    if image_scale != 1 or (viewer_size[0] >= scaled_size[0] and viewer_size[1] >= scaled_size[1]):
        return scaled_size
    if viewer_size[0] / scaled_size[0] < viewer_size[1] / scaled_size[1]:
        return viewer_size[0], viewer_size[0] * scaled_size[1] / scaled_size[0]
    else:
        return viewer_size[1] * scaled_size[0] / scaled_size[1], viewer_size[1]


loop = EventLoop()
loop.run(main_frame)
