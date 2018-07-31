from asyncframes import Awaitable

pressed = set()

class Key(Awaitable):
	def __init__(self, name):
		self.name = name
		self.isdown = False
		self.ispressed = False

Escape = Key('Escape')
Return = Key('Return')
Left = Key('Left')
Right = Key('Right')
Up = Key('Up')
Down = Key('Down')

def onkeydown(key):
	key.isdown = True
	key.ispressed = True
	pressed.add(key)
	key.raise_event()

def onkeyup(key):
	key.isdown = False

def onupdate():
	for key in pressed:
		key.ispressed = False
	pressed.clear()
