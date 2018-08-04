import abc
from enum import Enum
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget, QMainWindow, QGroupBox, QLayout, QHBoxLayout, QVBoxLayout, QGridLayout
from PyQt5.QtCore import QObject, Qt
from asyncframes import run, define_frame, Awaitable, Event, Frame, Primitive, hold, sleep, any_
import keys

class Layout(Enum):
	hbox = QHBoxLayout
	vbox = QVBoxLayout
	grid = QGridLayout

class WFrameMeta(type(QObject), abc.ABCMeta):
	pass

@define_frame
class WLFrame(Frame):
	def __init__(self, layout, size=None):
		super().__init__()

		# Find parent frame of type WLFrame -> self._wparent
		self._wparent = self._parent
		while self._wparent and not isinstance(self._wparent, WLFrame):
			self._wparent = self._wparent._parent

		if not self._wparent and not isinstance(self, WFrame):
			raise Exception(self.__class__.__name__ + " can't be defined outside WFrame")

		if layout is None: # If this frame doesn't use a layout
			self.layout = None
			if isinstance(self, WFrame): # If this frame is a window without a layout
				self.widget = QWidget()
			elif isinstance(self, WGFrame) and self._wparent.layout is not None: # If this frame is a container widget without a layout inside a panel or window with a layout
				self.widget = QGroupBox(self._wparent.widget)
				self._wparent.layout.addWidget(self.widget)
			elif isinstance(self, WGFrame) and self._wparent.layout is None: # If this frame is a container widget without a layout inside a panel or window without a layout
				self.widget = QGroupBox(self._wparent.widget)
			elif self._wparent.layout is not None: # If this frame is a panel without a layout inside a panel or window with a layout
				self.widget = QWidget(self._wparent.widget)
				self._wparent.layout.addWidget(self.widget)
			else: # If this frame is a panel without a layout inside a panel or window without a layout
				self.widget = self._wparent.widget
		else: # If this frame uses a layout
			self.layout = layout.value()
			if isinstance(self, WFrame): # If this frame is a window with a layout
				self.widget = QWidget()
				self.widget.setLayout(self.layout)
			elif isinstance(self, WGFrame) and self._wparent.layout is not None: # If this frame is a container widget with a layout inside a panel or window with a layout
				self.widget = QGroupBox(self._wparent.widget)
				self._wparent.layout.addWidget(self.widget)
				self.widget.setLayout(self.layout)
			elif isinstance(self, WGFrame) and self._wparent.layout is None: # If this frame is a container widget with a layout inside a panel or window without a layout
				self.widget = QGroupBox(self._wparent.widget)
				self.widget.setLayout(self.layout)
			elif self._wparent.layout is not None: # If this frame is a panel with a layout inside a panel or window with a layout
				self.widget = self._wparent.widget
				self._wparent.layout.addItem(self.layout)
			else: # If this frame is a panel with a layout inside a panel or window without a layout
				self.widget = QWidget(self._wparent.widget)
				self.widget.setLayout(self.layout)
				self.widget.show()

		if size and not isinstance(self, WFrame): # If this frame is a panel and size is defined
			#self.widget.setGeometry(300, 300, *size)
			self.widget.resize(*size)
		if self._wparent and isinstance(self, WFrame): # If this frame is a window with a parent WLFrame
			self.setWindowModality(Qt.ApplicationModal) # Disable the parent window while this window is open

	def remove(self):
		# Find parent frame of type WLFrame -> self._wparent
		self._wparent = self._parent
		while self._wparent and not isinstance(self._wparent, WLFrame):
			self._wparent = self._wparent._parent

		if self._wparent and self.widget != self._wparent.widget:
			#TODO: Remove widget from layout
			self.widget.setParent(None)
			self.widget.deleteLater()
		super().remove()

@define_frame(123) #TODO: Explore usages for define_frame arguments
class WFrame(WLFrame, QMainWindow, metaclass=WFrameMeta):
	def __init__(self, size=None, title=None, layout=None):
		QMainWindow.__init__(self)
		super().__init__(layout, size)
		if size:
			#self.setGeometry(300, 300, *size)
			self.resize(*size)
		if title is not None:
			self.setWindowTitle(title)
		self.setCentralWidget(self.widget)
		self.show()
		self.closed = Awaitable("WFrame.closed")

	def closeEvent(self, event):
		self.remove()
		Event(self, self.closed, event).process()

	_keymap = {
		16777216: keys.escape,
		16777220: keys.enter,
		16777234: keys.left,
		16777236: keys.right,
		16777235: keys.up,
		16777237: keys.down
	}
	def keyPressEvent(self, event):
		try:
			keys.onkeydown(WFrame._keymap[event.key()], self, event)
		except KeyError:
			print("Unknown keycode: " + str(event.key()))
	def keyReleaseEvent(self, event):
		try:
			keys.onkeyup(WFrame._keymap[event.key()], self, event)
		except KeyError:
			print("Unknown keycode: " + str(event.key()))

@define_frame
class WGFrame(WLFrame):
	def __init__(self, size=None, title=None, layout=None):
		super().__init__(layout, size)
		self.widget.setTitle(title)
		self.widget.show()
