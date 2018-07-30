import abc
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QLayout, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import QObject
from asyncframes import run, sleep, define_frame, Frame
import keys

class WFrameMeta(type(QObject), abc.ABCMeta):
	pass

@define_frame(123)
class WFrame(Frame, QMainWindow, metaclass=WFrameMeta):
	def __init__(self, framefunc, *frameargs, **framekwargs):
		super().__init__(framefunc, *frameargs, **framekwargs)

		QMainWindow.__init__(self)
		self.setWindowTitle('TODO')
		self.widget = QWidget()
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


if __name__ == "__main__":
	@WFrame(size=(800, 600))
	async def main():
		await keys.Escape#sleep(1)

	run(main)
