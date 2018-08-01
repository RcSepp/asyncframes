from asyncframes import Awaitable

pressed = set()

class Key(Awaitable):
	def __init__(self, name):
		super().__init__()
		self.name = name
		self.isdown = False
		self.ispressed = False
	def __str__(self):
		return self.name + " key"

class AnyKey(Key):
	def __init__(self):
		super().__init__('any')
	def __await__(self):
		msg = yield(self) #TODO: Value sended by yield (self) not required
		while not isinstance(msg, Key):
			msg = yield(self) #TODO: Value sended by yield (self) not required
		return msg

escape = Key('escape')
enter = Key('enter')
left = Key('left')
right = Key('right')
up = Key('up')
down = Key('down')
anykey = AnyKey()

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
		print(await keys.anykey)
	run(main)
