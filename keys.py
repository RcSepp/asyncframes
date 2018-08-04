from asyncframes import Awaitable, Event

pressed = set()

class Key(Awaitable):
	def __init__(self, name):
		super().__init__(name + " key")
		self.name = name
		self.isdown = False
		self.ispressed = False

class AnyKey(Key):
	def __init__(self):
		super().__init__('any')
	def step(self, msg=None):
		if msg and isinstance(msg.target, Key):
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self

escape = Key('escape')
enter = Key('enter')
left = Key('left')
right = Key('right')
up = Key('up')
down = Key('down')
anykey = AnyKey()

def onkeydown(key, eventsender, eventargs):
	key.isdown = True
	key.ispressed = True
	pressed.add(key)
	Event(eventsender, key, eventargs).process()

def onkeyup(key, eventsender, eventargs):
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
		print(str((await keys.anykey).target) + " pressed")
	run(main)
