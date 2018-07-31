import abc
from enum import Enum
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget, QMainWindow, QLayout, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import QObject
from asyncframes import run, define_frame, Awaitable, Frame, Primitive, hold
import keys

class Layout(Enum):
	hbox = QHBoxLayout
	vbox = QVBoxLayout

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

		if layout is None: # If this frame doesn't use a layout
			self.layout = None
			if self._wparent is None: # If this frame is a window without a layout
				self.widget = QWidget()
			elif self._wparent.layout is not None: # If this frame is a panel without a layout inside a panel or window with a layout
				self.widget = QWidget(self._wparent.widget)
				self._wparent.layout.addWidget(self.widget)
			else: # If this frame is a panel without a layout inside a panel or window without a layout
				self.widget = self._wparent.widget
		else: # If this frame uses a layout
			self.layout = layout.value()
			if self._wparent is None: # If this frame is a window with a layout
				self.widget = QWidget()
				self.widget.setLayout(self.layout)
			elif self._wparent.layout is not None: # If this frame is a panel with a layout inside a panel or window with a layout
				self.widget = self._wparent.widget
				self._wparent.layout.addItem(self.layout)
			else: # If this frame is a panel with a layout inside a panel or window without a layout
				self.widget = QWidget(self._wparent.widget)
				self.widget.setLayout(self.layout)
				self.widget.show()

		if size and self._wparent is not None: # If this frame is a panel and size is defined
			#self.widget.setGeometry(300, 300, *size)
			self.widget.resize(*size)

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

@define_frame(123)
class WFrame(WLFrame, QMainWindow, metaclass=WFrameMeta):
	def __init__(self, size=None, title=None, layout=None):
		super().__init__(layout, size)

		QMainWindow.__init__(self)
		if size:
			#self.setGeometry(300, 300, *size)
			self.resize(*size)
		if title is not None:
			self.setWindowTitle(title)
		self.setCentralWidget(self.widget)
		self.show()

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
			keys.onkeydown(WFrame._keymap[event.key()])
		except KeyError:
			print("Unknown keycode: " + str(event.key()))
	def keyReleaseEvent(self, event):
		try:
			keys.onkeyup(WFrame._keymap[event.key()])
		except KeyError:
			print("Unknown keycode: " + str(event.key()))

class Widget(Primitive):
	def __init__(self):
		super().__init__(WLFrame)

	def _show(self, pos):
		self.qtwidget.resize(self.qtwidget.sizeHint())
		if pos is not None: self.qtwidget.move(pos.x, pos.y)
		if self._owner.layout is not None:
			self._owner.layout.addWidget(self.qtwidget)
		self.qtwidget.show()

	def remove(self):
		if self._owner.layout is not None:
			self._owner.layout.removeWidget(self.qtwidget)
		self.qtwidget.setParent(None)
		self.qtwidget.deleteLater()
		super().remove()

class Button(Widget):
	def __init__(self, text="Button", pos=None):
		super().__init__()
		self.qtwidget = QtWidgets.QPushButton(text, self._owner.widget)
		self.click = Awaitable()
		self.qtwidget.clicked.connect(self.click.raise_event)
		self._show(pos)

class ProgressBar(Widget):
	def __init__(self, pos=None):
		super().__init__()
		self.qtwidget = QtWidgets.QProgressBar(self._owner.widget)
		self._show(pos)

	@property
	def value(self):
		return self.qtwidget.value()
	@value.setter
	def value(self, value):
		return self.qtwidget.setValue(value)

if __name__ == "__main__":
	@WFrame(size=(200, 100), title="gui", layout=Layout.vbox)
	async def main():
		btn = Button()
		intermediate_frame()
		await btn.click#keys.escape#sleep(1)

	@Frame
	async def intermediate_frame():
		main_layout()
		await hold()

	@WLFrame(Layout.hbox, size=(200, 100))
	async def main_layout():
		ProgressBar()
		ProgressBar()
		await hold()

	run(main)
