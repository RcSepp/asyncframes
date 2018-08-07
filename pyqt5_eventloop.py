import collections
import logging
import sys
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import asyncframes


log = logging.getLogger(__name__)
if False:
	log.setLevel(logging.DEBUG)


loghandler = logging.StreamHandler(sys.stdout)
loghandler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(message)s")#('%(relativeCreated)d - %(name)s - %(levelname)s - %(message)s')
loghandler.setFormatter(formatter)
log.addHandler(loghandler)


class EventLoop(asyncframes.EventLoop):
	def __init__(self):
		self.qt = QApplication.instance() or QApplication(sys.argv)

		try:
			import qdarkstyle
		except ImportError:
			pass
		else:
			self.qt.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

	def run(self, frame):
		if asyncframes.EventLoop._current is not None:
			raise Exception("Another event loop is already running")
		asyncframes.EventLoop._current = self
		self._frame_register = {}

		try:
			self.mainframe = frame()
			if not self.mainframe._removed:
				try:
					self.qt.exec_()
				except:
					logging.exception(traceback.format_exc())
		except:
			asyncframes.EventLoop._current = None
			asyncframes.Frame._current = None
			self._frame_register = None
			raise
		else:
			asyncframes.EventLoop._current = None
			asyncframes.Frame._current = None
			self._frame_register = None

	def sendevent(self, event):
		# Discard events sent after the event loop has been closed
		if self != asyncframes.EventLoop._current: return

		try:
			targetframe = self._frame_register.pop(event.target)
		except KeyError:
			log.debug("Ignoring event {}".format(event)) # Ignore unawaited event
		else:
			log.debug("Processing event {}".format(event))
			try:
				awaitable = targetframe.step(event)
			except (StopIteration, GeneratorExit):
				if targetframe == self.mainframe: # If the main frame finished
					log.debug("Main frame finished")
					QApplication.instance().exit()
					return False
				else:
					log.debug("Frame {} finished".format(targetframe))
			else:
				self.register_frame(targetframe, awaitable)

		return True

	def postevent(self, event, delay=0):
		# Discard events sent after the event loop has been closed
		if self != asyncframes.EventLoop._current: return

		QTimer.singleShot(1000 * delay, lambda: self.sendevent(event))

	def register_frame(self, frame, awaitable):
		log.debug("Frame {} awaits event {}".format(frame, awaitable))
		if isinstance(awaitable, collections.Iterable):
			for a in awaitable:
				self._frame_register[a] = frame
		else:
			self._frame_register[awaitable] = frame

if __name__ == "__main__":
	from asyncframes import define_frame, Frame, Primitive, sleep

	@define_frame
	class MyFrame1(Frame):
		pass
	@define_frame
	class MyFrame2(Frame):
		pass

	class MyPrimitive(Primitive):
		def __init__(self):
			super().__init__(MyFrame1)

	@MyFrame1
	async def frameA():
		frameB(0.1, '1')
		await frameB(0.2, '2')
		print('DONE')

	@MyFrame2
	async def frameB(seconds, name):
		p = MyPrimitive()
		await sleep(seconds)
		print(name)

	loop = EventLoop()
	loop.run(frameA)
