from PyQt5 import QtWidgets, QtCore
from asyncframes import Awaitable, Primitive, hold, sleep, any_
from gui import WLFrame

class Widget(Primitive):
	def __init__(self):
		super().__init__(WLFrame)

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

	def remove(self):
		if self._owner.layout is not None:
			self._owner.layout.removeWidget(self)
		self.setParent(None)
		self.deleteLater()
		super().remove()

	def _convert_all_signals_to_awaitables(self):
		for key in dir(self):
			signal = getattr(self, key)
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
	
	@property
	def text(self):
		return QtWidgets.QLabel.text(self)
	@text.setter
	def text(self, value):
		QtWidgets.QLabel.setText(self, value)

class Button(Widget, QtWidgets.QPushButton):
	def __init__(self, text="Button", pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QPushButton.__init__(self, text, self._owner.widget)
		self._convert_all_signals_to_awaitables()
		self._show(pos, row, col, rowspan, colspan)
	
	@property
	def text(self):
		return QtWidgets.QPushButton.text(self)
	@text.setter
	def text(self, value):
		QtWidgets.QPushButton.setText(self, value)

class ProgressBar(Widget, QtWidgets.QProgressBar):
	def __init__(self, pos=None, row=None, col=None, rowspan=1, colspan=1):
		super().__init__()
		QtWidgets.QProgressBar.__init__(self, self._owner.widget)
		self._convert_all_signals_to_awaitables()
		self._show(pos, row, col, rowspan, colspan)

	@property
	def value(self):
		return QtWidgets.QProgressBar.value(self)
	@value.setter
	def value(self, value):
		return QtWidgets.QProgressBar.setValue(self, value)

class Action(Widget, QtWidgets.QAction):
	def __init__(self, text):
		super().__init__()
		QtWidgets.QAction.__init__(self)
		self.setText(text)
		self.setParent(self._owner.widget)
		self._convert_all_signals_to_awaitables()


if __name__ == "__main__":
	from asyncframes import run, hold, sleep, any_
	from gui import WFrame, WGFrame, Layout

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

	run(main)
