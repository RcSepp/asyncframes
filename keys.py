from asyncframes import Awaitable

pressed = set()

class Key(Awaitable):
	def __init__(self, name):
		self.name = name
		self.isdown = False
		self.ispressed = False
	def __str__(self):
		return self.name + " key"

class AnyKey(Key):
	def __init__(self):
		super().__init__('Any')
	def __await__(self):
		msg = yield(self) #TODO: Value sended by yield (self) not required
		while not isinstance(msg, Key):
			msg = yield(self) #TODO: Value sended by yield (self) not required
		return msg

Escape = Key('Escape')
Return = Key('Return')
Left = Key('Left')
Right = Key('Right')
Up = Key('Up')
Down = Key('Down')
Any = AnyKey()

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

if __name__ == "__main__":
	from asyncframes import run
	from gui import WFrame
	import keys
	@WFrame
	async def main():
		print(await keys.Any)
	run(main)
