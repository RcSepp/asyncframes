from PyQt5 import QtWidgets, QtCore
from asyncframes import Awaitable, Primitive, hold, sleep, any_
from gui import Frame, WLFrame, Layout

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

class Label(Widget, QtWidgets.QLabel):
	def __init__(self, text="Label", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QLabel.__init__(self, text, self._owner.widget)
		_convert_all_signals_to_awaitables(self)
		self._show(pos, row, col, rowspan, colspan)

class Button(Widget, QtWidgets.QPushButton):
	def __init__(self, text="Button", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QPushButton.__init__(self, text, self._owner.widget)
		_convert_all_signals_to_awaitables(self)
		self._show(pos, row, col, rowspan, colspan)

class ProgressBar(Widget, QtWidgets.QProgressBar):
	def __init__(self, pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QProgressBar.__init__(self, self._owner.widget)
		_convert_all_signals_to_awaitables(self)
		self._show(pos, row, col, rowspan, colspan)

class PlainTextEdit(Widget, QtWidgets.QPlainTextEdit):
	def __init__(self, pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QPlainTextEdit.__init__(self, self._owner.widget)
		_convert_all_signals_to_awaitables(self)
		self._show(pos, row, col, rowspan, colspan)

class Action(Primitive, QtWidgets.QAction):
	def __init__(self, text):
		super().__init__(WLFrame)
		QtWidgets.QAction.__init__(self, text, self._owner.widget)
		_convert_all_signals_to_awaitables(self)

def stretch(stretch):
	# Find parent frame of class WLFrame
	wframe = Frame._current
	while wframe and not issubclass(type(wframe), WLFrame):
		wframe = wframe._parent
	if not wframe:
		raise Exception("stretch() can't be defined outside WLFrame")
	if type(wframe.layout) != QtWidgets.QHBoxLayout and type(wframe.layout) != QtWidgets.QVBoxLayout:
		raise Exception("stretch() can only be defined inside a WLFrame with hbox or vbox layout")

	wframe.layout.addStretch(stretch)

def enable_widget_properties():
	import inspect
	import re
	import sys
	
	def create_properties(src, dest):
		"""
		Substitute getter/setter pairs with Python properties

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
	
	for clsname, cls in inspect.getmembers(sys.modules[__name__], inspect.isclass): # For each class in current module
		if cls != Widget and issubclass(cls, Primitive): # If class is subclass of Primitive
			for basecls in inspect.getmro(cls): # For each class in inheritance hierarchy of cls
				if basecls != Widget and basecls != cls and issubclass(basecls, QtCore.QObject): # Find highest base class that inherits from QObject
					create_properties(basecls, cls) # Substitute getter/setter pairs of basecls with Python properties in cls
					break

def _convert_all_signals_to_awaitables(obj):
	for key in dir(obj.__class__):
		try:
			signal = getattr(obj, key)
		except TypeError:
			continue
		if type(signal) == QtCore.pyqtBoundSignal:
			awaitable = Awaitable("{}.{}".format(obj.__class__.__name__, key), signal, obj)
			awaitable.connect = signal.connect # Preserve pyqtBoundSignal.connect()
			awaitable.emit = signal.emit # Preserve pyqtBoundSignal.emit()
			setattr(obj, key, awaitable)

if __name__ == "__main__":
	from asyncframes import hold, sleep, any_
	from gui import WFrame, WGFrame, Layout
	from pyqt5_eventloop import EventLoop

	enable_widget_properties()

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
