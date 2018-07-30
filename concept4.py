import types

@types.coroutine
def sleep():
	yield 1
	yield 2
	yield 3

@types.coroutine
def foo():
	b = bar()
	while True:
		print('activate')
		try:
			result = b.send(None)
		except StopIteration:
			print('deactivate')
			break
		else:
			print('deactivate')
			yield result

async def bar():
	await sleep()

c = foo()
print(dir(c))
print(c.send(None))
print(c.send(None))
print(c.send(None))
print(c.send(None))
