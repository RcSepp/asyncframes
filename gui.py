import abc
from enum import Enum
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget, QMainWindow, QLayout, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import QObject
from asyncframes import run, define_frame, Awaitable, Frame, Primitive
import keys

class Layout(Enum):
	hbox = QHBoxLayout
	vbox = QVBoxLayout

class WFrameMeta(type(QObject), abc.ABCMeta):
	pass

@define_frame(123)
class WFrame(Frame, QMainWindow, metaclass=WFrameMeta):
	def __init__(self, size=None, title=None, layout=None):
		super().__init__()

		QMainWindow.__init__(self)
		if size:
			#self.setGeometry(300, 300, *size)
			self.resize(*size)
		if title is not None:
			self.setWindowTitle(title)
		self.widget = QWidget()
		if layout is not None:
			self.layout = layout.value()
			self.widget.setLayout(self.layout)
		else:
			self.layout = None
		self.setCentralWidget(self.widget)
		self.show()

	_keymap = {
		16777216: keys.Escape,
		16777220: keys.Return,
		16777234: keys.Left,
		16777236: keys.Right,
		16777235: keys.Up,
		16777237: keys.Down
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
		super().__init__(WFrame)

	def _show(self, pos):
		self.qtwidget.resize(self.qtwidget.sizeHint())
		if pos is not None: self.qtwidget.move(pos.x, pos.y)
		if self._owner.layout is not None:
			self._owner.layout.addWidget(self.qtwidget)
		else:
			self.qtwidget.show()

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
	@WFrame(size=(200, 50), title="gui", layout=Layout.hbox)
	async def main():
		pb = ProgressBar()
		btn = Button()
		await btn.click#keys.Escape#sleep(1)

	run(main)
