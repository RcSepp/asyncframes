import types

@types.coroutine
def sleep(seconds):
	yield 123

async def other():
	await sleep(1)

@types.coroutine
def other2():
	yield from sleep(1)

o = other2()
print('DONE')