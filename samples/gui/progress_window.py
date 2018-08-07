from asyncframes import Frame, sleep
from pyqt5_eventloop import EventLoop
from gui import WFrame, Layout
from gui.widgets import Button, ProgressBar

@Frame
async def main():
	# Start an arbitrary process in the background
	p = process()

	# Show a wframe to monitor progress and wait until it finishes
	await dialog(p)

	# If the process hasn't finished already, destroy it manually
	# Note: This function isn't necessary here, since any frame is automatically removed when it goes out of scope.
	p.remove()

@Frame
async def process(self):
	"""
	This frame simulates a time consuming process (i.e. a file copy operation).
	It reports information about its own progress through the self.progress variable (range: 0 to 100).
	The frame exits once the process is completed.
	This process simply advances its progress by 1% every 100ms (total runtime: 100 * 100ms = 10s)
	"""
	self.progress = 0 # Progress in %
	while self.progress < 100:
		self.progress += 1
		await sleep(0.1)

@Frame
async def monitor_progress(p, pb):
	"""
	This frame synchronizes progress with the value of a progress bar.
	It exits once progress reaches 100%.
	"""
	while p.progress < 100:
		pb.value = p.progress
		await sleep() # Make this a non-blocking loop
	pb.value = 100

@WFrame(size=(400, 50), layout=Layout.hbox)
async def dialog(p):
	"""
	This frame shows a progress dialog with a progress bar and a cancel button.
	It exits once the monitored process finishes or the cancel button is pressed.
	"""
	# Create dialog controls
	pg_progress = ProgressBar()
	cmd_cancel = Button("Cancel")

	# Wait until either monitor_progress finishes or cmd_cancel is clicked
	await (monitor_progress(p, pg_progress) | cmd_cancel.clicked)

	# Close dialog

loop = EventLoop()
loop.run(main)
