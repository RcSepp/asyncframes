import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import asyncframes


class EventLoop(asyncframes.EventLoop):
	def __init__(self):
		self.qt = QApplication.instance() or QApplication([])

		try:
			import qdarkstyle
		except ImportError:
			pass
		else:
			self.qt.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

	def _run(self):
		try:
			self.qt.exec_()
		except:
			print(traceback.format_exc())

	def _stop(self):
		QApplication.instance().exit()

	def _post(self, event, delay):
		QTimer.singleShot(1000 * delay, lambda: self.sendevent(event))
