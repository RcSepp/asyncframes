import types

@types.coroutine
def sleep():
	y = (yield)
	yield 2

async def coroutine():
	print(await other())
	print(3)

async def other():
	await sleep()
	return 1

c = coroutine()
print(c.send(None))
print(c.send(None))
print(c.send(None))


#See: https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/