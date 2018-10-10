# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import abc
import functools
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QThread, QObject, Qt
from PyQt5.Qt import pyqtSlot, Q_ARG
import asyncframes


class EventLoopMeta(type(QObject), abc.ABCMeta):
	pass
class EventLoop(asyncframes.AbstractEventLoop, QObject, metaclass=EventLoopMeta):
    # Start Qt
    qt = QApplication.instance() or QApplication([])

    def __init__(self):
        asyncframes.AbstractEventLoop.__init__(self)
        QObject.__init__(self)
        self.moveToThread(QThread.currentThread())

    def _run(self):
        try:
            try:
                # Execute QThread event loop
                self.loop = QThread.currentThread()
                self.loop.exec_() # If the current thread is the main thread, this will throw a RuntimeError
            except RuntimeError:
                # Execute QApplication event loop
                self.loop = EventLoop.qt
                EventLoop.qt.exec_()
        except: # pragma: no cover
            print(traceback.format_exc()) # pragma: no cover

    def _stop(self):
        self.loop.exit()

    def _close(self):
        pass

    def _post(self, delay, callback, args):
        QTimer.singleShot(1000 * delay, functools.partial(callback, *args))
    
    def _invoke(self, delay, callback, args):
        self.metaObject().invokeMethod(self, "_invoke_slot", Qt.QueuedConnection, Q_ARG(float, delay), Q_ARG(object, functools.partial(callback, *args)))

    @pyqtSlot(float, object)
    def _invoke_slot(self, delay, callback):
        QTimer.singleShot(1000 * delay, callback)

    def _spawnthread(self, target, args):
        class Thread(QThread):
            def __init__(self, target, args):
                super().__init__()
                self.target = target
                self.args = args
            def run(self):
                try:
                    self.target(*self.args)
                except:
                    print(traceback.format_exc()) # pragma: no cover
        thread = Thread(target, args)
        thread.start()
        return thread

    def _jointhread(self, thread):
        thread.wait()
