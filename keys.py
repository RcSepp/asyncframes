from asyncframes import Awaitable, Event

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
	def step(self, msg=None):
		if msg and isinstance(msg.receiver, Key):
			stop = StopIteration()
			stop.value = msg
			raise stop
		return self #TODO: Return value "self" not required

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
	Event(eventsender, key, eventargs).post()

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
		print((await keys.anykey).receiver)
	run(main)
