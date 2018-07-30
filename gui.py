import abc
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QLayout, QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import QObject
from asyncframes import run, sleep, define_frame, Frame

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

@WFrame(size=(800, 600))
async def main():
	await sleep(1)

run(main)