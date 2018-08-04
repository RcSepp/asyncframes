from PyQt5 import QtWidgets
from asyncframes import Awaitable, Primitive, hold, sleep, any_
from gui import WLFrame

class Widget(Primitive):
	def __init__(self):
		super().__init__(WLFrame)

	def _show(self, pos, row, col, rowspan, colspan):
		self.qtwidget.resize(self.qtwidget.sizeHint())
		if pos is not None: self.qtwidget.move(pos.x, pos.y)
		if self._owner.layout is not None:
			if isinstance(self._owner.layout, QtWidgets.QGridLayout):
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
			clicked_button = (await any_(*[button.click for button in examples.keys()])).sender
			await examples[clicked_button]()

	run(main)
