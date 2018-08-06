import re
from PyQt5 import QtWidgets, QtCore
from asyncframes import Awaitable, Primitive, hold, sleep, any_
from gui import WLFrame

def _create_properties(src, dest):
	"""
	Substitude getter/setter pairs with Python properties

	Find callable attributes of the form 'foo' (getter) and 'setFoo' (setter) in class src and replace them with properties in class dest.
	"""
	setters = {}
	setter_regex = re.compile(r"set[A-Z]\w*")
	for key in dir(src):
		try:
			setter = getattr(src, key)
		except TypeError:
			continue
		if callable(setter) and setter_regex.match(key):
			setters[key[3].lower() + key[4:]] = setter
	for key in dir(src):
		try:
			getter = getattr(src, key)
		except TypeError:
			continue
		if callable(getter) and key in setters:
			setattr(dest, key, property(getter, setters[key])) # Overwrite getter with property

class Widget(Primitive):
	def __init__(self):
		super().__init__(WLFrame)

	def remove(self):
		if self._owner.layout is not None:
			self._owner.layout.removeWidget(self)
		self.setParent(None)
		self.deleteLater()
		super().remove()

	def _show(self, pos, row, col, rowspan, colspan):
		self.resize(self.sizeHint())
		if pos is not None: self.move(pos.x, pos.y)
		if self._owner.layout is not None:
			if isinstance(self._owner.layout, QtWidgets.QGridLayout):
				if row is not None and col is not None:
					self._owner.layout.addWidget(self, row, col, rowspan, colspan)
				else:
					self._owner.layout.addWidget(self)
			else:
				self._owner.layout.addWidget(self)
		self.show()

	def _convert_all_signals_to_awaitables(self):
		for key in dir(self.__class__):
			try:
				signal = getattr(self, key)
			except TypeError:
				continue
			if type(signal) == QtCore.pyqtBoundSignal:
				awaitable = Awaitable("{}.{}".format(self.__class__.__name__, key), signal, self)
				awaitable.connect = signal.connect # Preserve pyqtBoundSignal.connect()
				awaitable.emit = signal.emit # Preserve pyqtBoundSignal.emit()
				setattr(self, key, awaitable)

class Label(Widget, QtWidgets.QLabel):
	def __init__(self, text="Label", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QLabel.__init__(self, text, self._owner.widget)
		self._convert_all_signals_to_awaitables()
		self._show(pos, row, col, rowspan, colspan)
_create_properties(QtWidgets.QLabel, Label)

class Button(Widget, QtWidgets.QPushButton):
	def __init__(self, text="Button", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QPushButton.__init__(self, text, self._owner.widget)
		self._convert_all_signals_to_awaitables()
		self._show(pos, row, col, rowspan, colspan)
_create_properties(QtWidgets.QPushButton, Button)

class ProgressBar(Widget, QtWidgets.QProgressBar):
	def __init__(self, pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QProgressBar.__init__(self, self._owner.widget)
		self._convert_all_signals_to_awaitables()
		self._show(pos, row, col, rowspan, colspan)
_create_properties(QtWidgets.QProgressBar, ProgressBar)

class Action(Widget, QtWidgets.QAction):
	def __init__(self, text):
		super().__init__()
		QtWidgets.QAction.__init__(self, text, self._owner.widget)
		self._convert_all_signals_to_awaitables()
_create_properties(QtWidgets.QAction, Action)


if __name__ == "__main__":
	from asyncframes import hold, sleep, any_
	from gui import WFrame, WGFrame, Layout
	from pyqt5_eventloop import EventLoop

	@WFrame(layout=Layout.hbox, title="group box")
	def groupbox_window():
		@WGFrame(title="group box", layout=Layout.hbox)
		def group_box():
			ProgressBar()
			ProgressBar()
		group_box()

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
			Button('WGFrame', row=1, col=0, colspan=2): groupbox_window,
		}
		
		while True:
			clicked_button = (await any_(*[button.clicked for button in examples.keys()])).sender
			await examples[clicked_button]()

	loop = EventLoop()
	loop.run(main)
