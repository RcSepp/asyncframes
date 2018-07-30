import asyncio
import datetime
from inspect import signature
import types


async def display_date():
	end_time = loop.time() + 5.0
	while True:
		print(datetime.datetime.now())
		if (loop.time() + 1.0) >= end_time:
			break
		await asyncio.sleep(1)


class Frame(object):
	_current = None

	def __init__(self, framefunc):
		self._framefunc = framefunc
		self.__name__ = framefunc.__name__

		self._parent = Frame._current
		if self._parent:
			self._parent._children.append(self)
		self._children = []

	@types.coroutine
	def run(self, *frameargs, **framekwargs):
		hasself = 'self' in signature(self._framefunc).parameters
		generator = self._framefunc(self, *frameargs, **framekwargs) if hasself else self._framefunc(*frameargs, **framekwargs)

		while True:
			Frame._current = self
			try:
				result = generator.send(None)
			except StopIteration:
				Frame._current = self._parent
				break
			else:
				Frame._current = self._parent
				yield result

	def remove(self):
		for child in self._children:
			child.remove()
		if self._parent:
			self._parent._children.remove(self)
		del self



def define_frame(frameclass):
	def createframefactory(frame):
		async def framefactory(*frameargs, **framekwargs):
			frameinstance = frameclass(frame)
			await frameinstance.run(*frameargs, **framekwargs)
			frameinstance.remove()
		return framefactory
	return createframefactory


@define_frame
class MyFrame(Frame):
	def __init__(self, framefunc):
		super().__init__(framefunc)
		print("creating frame " + self.__name__)
	def remove(self):
		print("removing frame " + self.__name__)
		super().remove()



@MyFrame
async def main():
	c1 = child('1')
	c2 = child('2')
	await asyncio.wait([c1, c2])
	print('DONE')

@MyFrame
async def child(self, c):
	print(c)
	await asyncio.sleep(0.5)
	print(c)
	await asyncio.sleep(0.5)
	print(c)
	await asyncio.sleep(0.5)



def run(future):
	global loop
	try:
		asyncio.run(future)
		#loop = asyncio.get_running_loop()
	except AttributeError:
		loop = asyncio.get_event_loop()
		loop.run_until_complete(future)
		loop.close()

run(main())