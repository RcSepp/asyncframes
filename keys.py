from asyncframes import Awaitable, update

pressed = set()

class Key(Awaitable):
	def __init__(self, name):
		self.name = name
		self.isdown = False
		self.ispressed = False
	def __await__(self):
		msg = yield(self) #TODO: Value sended by yield (self) not required
		while msg != self:
			msg = yield(self) #TODO: Value sended by yield (self) not required

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
	update(key)

def onkeyup(key):
	key.isdown = False

def onupdate():
	for key in pressed:
		key.ispressed = False
	pressed.clear()
