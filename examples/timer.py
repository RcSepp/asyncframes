from asyncframes import Frame, EventSource, sleep
from asyncframes.asyncio_eventloop import EventLoop

@Frame
async def timer(self, interval):
    # Initialization code
    self.tick = EventSource('timer.tick')

    # Main code
    while True:
        await sleep(1)
        self.tick.post(self)

@Frame
async def main_frame():
    tmr = timer(1)
    await tmr.ready

    for i in range(5):
        await tmr.tick
        print(i + 1)

loop = EventLoop()
loop.run(main_frame)