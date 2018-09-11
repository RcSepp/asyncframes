# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import functools
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import asyncframes


class EventLoop(asyncframes.AbstractEventLoop):
    def __init__(self):
        super().__init__()
        self.qt = QApplication.instance() or QApplication([])

    def _run(self):
        try:
            self.qt.exec_()
        except: # pragma: no cover
            print(traceback.format_exc()) # pragma: no cover

    def _stop(self):
        QApplication.instance().exit()

    def _post(self, event, delay):
        QTimer.singleShot(1000 * delay, functools.partial(self.sendevent, event))
