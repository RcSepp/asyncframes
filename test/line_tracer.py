import enum
import io
import linecache
import os.path
import threading
import sys
from asyncframes import get_current_eventloop_index, _THREAD_LOCALS

class Trace(object):
    BASE_DIR = os.path.realpath("..")
    SKIP_FILES = set([
        "test/line_tracer.py",
        "asyncframes/asyncio_eventloop.py",
        "asyncframes/pyqt5_eventloop.py",
        "asyncframes/__init__.py"
    ])
    SKIP_FUNCTIONS = {
        "test/test_asyncframes.py": set([
            "TimedFormatter.format"
        ]),
        "asyncframes/__init__.py": set([
            "worker_thread",
            "EventLoop.__init__",
            "EventLoop._spawnthread",
            "EventLoop.<listcomp>",
            "Frame.__init__",
            "Event.__init__",
            "Event.__bool__",
            "Event.send",
            "Frame.removed"
        ])
    }

    class Mode(enum.Enum):
        on_error = 0 # Output full trace when traced function failed
        on_done = 1 # Output full trace when traced function finished
        in_situ = 2 # Output trace while traced function is running

    def __init__(self, trace_mode, output_file, check_affinity):
        self.trace_mode = trace_mode
        self.trace_stream = open(output_file, 'w') if output_file else io.StringIO()
        self.check_affinity = check_affinity
        self.old_trace = None

    def _trace(self, frame, event, arg):
        # Discard any events besides line stepping
        if event != "line":
            return self._trace

        # Discard trace events outside BASE_DIR
        filename = frame.f_code.co_filename
        if not filename.startswith(Trace.BASE_DIR):
            return self._trace

        # Discard trace events from files in SKIP_FILES
        fname = filename[len(Trace.BASE_DIR) + 1:]
        if fname in Trace.SKIP_FILES:
            return self._trace

        # Discard trace events from generator expressions and functions in SKIP_FUNCTIONS[fname]
        coname = frame.f_code.co_name
        if 'self' in frame.f_locals:
            coname = frame.f_locals['self'].__class__.__name__ + '.' + coname
        if coname == "<genexpr>" or (fname in Trace.SKIP_FUNCTIONS and coname in Trace.SKIP_FUNCTIONS[fname]):
            return self._trace

        # Get line stats
        lineno = frame.f_lineno
        line = linecache.getline(filename, lineno).lstrip()
        threadno = get_current_eventloop_index()

        # Log line stats
        if self.trace_mode == Trace.Mode.in_situ:
            print('thread {} | "{}", line {}, in {}:'.format(threadno, fname, lineno, coname).ljust(80) + line, end='')
        elif self.trace_stream:
            self.trace_stream.write('thread {} | "{}", line {}, in {}:'.format(threadno, fname, lineno, coname).ljust(80) + line)

        # Check frame eventloop affinity against current eventloop
        if self.check_affinity and getattr(_THREAD_LOCALS, '_current_frame', None) and \
            _THREAD_LOCALS._current_frame._eventloop_affinity and \
            _THREAD_LOCALS._current_frame._eventloop_affinity != _THREAD_LOCALS._current_eventloop and \
            fname == "test/test_asyncframes.py":
            raise AssertionError('eventloop affinity error: thread {} | "{}", line {}, in {}: {}'.format(threadno, fname, lineno, coname, line))

        return self._trace

    def __enter__(self):
        # Enable trace
        self.old_trace = None
        try:
            import pydevd
            debugger = pydevd.GetGlobalDebugger()
            if debugger is not None:
                self.old_trace = debugger.trace_dispatch
        except ImportError:
            pass
        if self.old_trace is None:
            self.old_trace = sys._getframe(0).f_trace
        sys.settrace(self._trace)
        threading.settrace(self._trace)

    def __exit__(self, exc_type, exc_value, traceback):
        # Disable trace
        if self.old_trace:
            sys.settrace(self.old_trace)

        if self.trace_mode == Trace.Mode.on_done or (exc_type is not None and self.trace_mode == Trace.Mode.on_error):
            if type(self.trace_stream) == io.StringIO:
                # Print string stream
                print(self.trace_stream.getvalue())

            # Close trace stream
            self.trace_stream.close()
            self.trace_stream = None
        else:
            # Reset trace stream
            self.trace_stream.truncate(0)
            self.trace_stream.seek(0)
