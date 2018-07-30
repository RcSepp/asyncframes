import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

qt = QApplication.instance() or QApplication(sys.argv)

def tick():
	print('tick')
	qt.exit()

QTimer.singleShot(1000, tick)

qt.exec_()