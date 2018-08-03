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
		Event(self, self.closed, event).post()

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

class Widget(Primitive):
	def __init__(self):
		super().__init__(WLFrame)

	def _show(self, pos, row, col, rowspan, colspan):
		self.qtwidget.resize(self.qtwidget.sizeHint())
		if pos is not None: self.qtwidget.move(pos.x, pos.y)
		if self._owner.layout is not None:
			if isinstance(self._owner.layout, QGridLayout):
				if row is not None and col is not None:
					self._owner.layout.addWidget(self.qtwidget, row, col, rowspan, colspan)
				else:
					self._owner.layout.addWidget(self.qtwidget)
			else:
				self._owner.layout.addWidget(self.qtwidget)
		self.qtwidget.show()

	def remove(self):
		if self._owner.layout is not None:
			self._owner.layout.removeWidget(self.qtwidget)
		self.qtwidget.setParent(None)
		self.qtwidget.deleteLater()
		super().remove()

class Label(Widget):
	def __init__(self, text="Label", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		self.qtwidget = QtWidgets.QLabel(text, self._owner.widget)
		self._show(pos, row, col, rowspan, colspan)
	
	@property
	def text(self):
		return self.qtwidget.text()
	@text.setter
	def text(self, value):
		self.qtwidget.setText(value)

class Button(Widget):
	def __init__(self, text="Button", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		self.qtwidget = QtWidgets.QPushButton(text, self._owner.widget)
		self.click = Awaitable("Button.click", self.qtwidget.clicked, self)
		self._show(pos, row, col, rowspan, colspan)
	
	@property
	def text(self):
		return self.qtwidget.text()
	@text.setter
	def text(self, value):
		self.qtwidget.setText(value)

class ProgressBar(Widget):
	def __init__(self, pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		self.qtwidget = QtWidgets.QProgressBar(self._owner.widget)
		self._show(pos, row, col, rowspan, colspan)

	@property
	def value(self):
		return self.qtwidget.value()
	@value.setter
	def value(self, value):
		return self.qtwidget.setValue(value)

if __name__ == "__main__":
	@WGFrame(size=(200, 100), title="group box", layout=Layout.hbox)
	def group_box():
		ProgressBar()
		ProgressBar()

	@WFrame(layout=Layout.hbox, title="hbox")
	def hbox_window():
		ProgressBar()
		ProgressBar()

	@WFrame(layout=Layout.vbox, title="vbox")
	def vbox_window():
		ProgressBar()
		ProgressBar()

	@WFrame(size=(200, 100), title="GUI examples", layout=Layout.grid)
	async def main():
		examples = {
			Button('Layout.hbox', row=0, col=0): hbox_window,
			Button('Layout.vbox', row=0, col=1): vbox_window,
			Button('WGFrame', row=1, col=0, colspan=2): group_box,
		}
		
		while True:
			clicked_button = (await any_(*[button.click for button in examples.keys()])).sender
			await examples[clicked_button]()

	run(main)
