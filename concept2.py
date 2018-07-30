import asyncio
import datetime
from inspect import signature
from collections.abc import Coroutine


async def display_date():
	end_time = loop.time() + 5.0
	while True:
		print(datetime.datetime.now())
		if (loop.time() + 1.0) >= end_time:
			break
		await asyncio.sleep(1)


class Frame(Coroutine):
	def __init__(self, framefunc, *frameargs, **framekwargs):
		self._framefunc = framefunc
		self.__name__ = framefunc.__name__
		super().__init__()

	async def run(self, *frameargs, **framekwargs):
		hasself = 'self' in signature(self._framefunc).parameters
		generator = self._framefunc(self, *frameargs, **framekwargs) if hasself else self._framefunc(*frameargs, **framekwargs)
		print(type(generator))
		#generator = asyncio.async(generator)
		#async for result in generator:
		#	print('x')#yield from result
		await generator

	# def __aiter__(self):
	# 	hasself = 'self' in signature(self._framefunc).parameters
	# 	self._generator = self._framefunc(self, *frameargs, **framekwargs) if hasself else self._framefunc(*frameargs, **framekwargs)
	# 	print('__aiter__')
	# 	return self
	# async def __anext__(self):
	# 	print('__anext__')
	# 	return self._generator



def define_frame(frameclass):
	def createframefactory(frame):
		async def framefactory(*frameargs, **framekwargs):
			frameinstance = frameclass(frame, *frameargs, **framekwargs)
			await frameinstance.run()
			# async for _ in frameinstance:
			# 	pass
			del frameinstance
		return framefactory
	return createframefactory


@define_frame
class MyFrame(Frame):
	def __init__(self, framefunc):
		super().__init__(framefunc)
		print("creating frame " + self.__name__)
	def __del__(self):
		print("removing frame " + self.__name__)



@MyFrame
async def main():
	c1 = child('1')
	c2 = child('2')
	await asyncio.gather(c1, c2)
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
		loop = asyncio.get_running_loop()
	except AttributeError:
		loop = asyncio.get_event_loop()
		loop.run_until_complete(future)
		loop.close()

run(main())