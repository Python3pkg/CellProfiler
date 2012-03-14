"""analysis.py - Run pipelines on imagesets to produce measurements.

CellProfiler is distributed under the GNU General Public License.
See the accompanying file LICENSE for details.

Copyright (c) 2003-2009 Massachusetts Institute of Technology
Copyright (c) 2009-2012 Broad Institute
All rights reserved.

Please see the AUTHORS file for credits.

Website: http://www.cellprofiler.org
"""
import sys
import os
import time
import optparse
import threading
import thread
import random
import zmq
import cStringIO as StringIO
import gc
import logging
import traceback

import cellprofiler.pipeline as cpp
import cellprofiler.workspace as cpw
import cellprofiler.measurements as cpmeas
from cellprofiler.gui.errordialog import ED_STOP, ED_SKIP
from cellprofiler.analysis import PipelineRequest, InitialMeasurementsRequest, WorkRequest, NoWorkReply, MeasurementsReport, InteractionRequest, DisplayRequest, ExceptionReport, InteractionReply, ServerExited, ImageSetSuccess, SharedDictionaryRequest, DictionaryReqRep, DictionaryReqRepRep, Ack
import subimager.client
from cellprofiler.utilities.rpdb import Rpdb

#
# CellProfiler expects NaN as a result during calculation
#
import numpy as np
np.seterr(all='ignore')

logger = logging.getLogger(__name__)


def main():
    # XXX - move all this to a class
    parser = optparse.OptionParser()
    parser.add_option("--work-announce",
                      dest="work_announce_address",
                      help="ZMQ port where work announcements are published",
                      default=None)
    parser.add_option("--subimager-port",
                      dest="subimager_port",
                      help="TCP port for subimager server",
                      default=None)
    options, args = parser.parse_args()

    if not (options.work_announce_address and options.subimager_port):
        parser.print_help()
        sys.exit(1)

    # set the subimager port
    subimager.client.port = options.subimager_port

    # Start the deadman switch thread.
    start_daemon_thread(target=exit_on_stdin_close, name="exit_on_stdin_close")

    # known work servers (analysis_id -> socket_address)
    work_servers = {}
    # their pipelines (analysis_id -> pipeline)
    pipelines = {}
    # their initial measurements (analysis_id -> measurements)
    initial_measurements = {}
    # lock for work_server and pipelines
    work_server_lock = threading.Lock()

    start_daemon_thread(target=listen_for_announcements,
                        args=(options.work_announce_address,
                              work_servers, pipelines, initial_measurements,
                              work_server_lock),
                        name="listen_for_announcements")

    zmq_context = zmq.Context()

    current_analysis_id = None

    # pipeline listener object
    pipeline_listener = PipelineEventListener()

    # Loop until exit
    while True:
        # no servers = no work
        if len(work_servers) == 0:
            time.sleep(.25)  # wait for work servers
            continue

        # find a server to connect to
        with work_server_lock:
            if len(work_servers) == 0:
                continue
            # continue to work with the same work server, if possible
            if current_analysis_id not in work_servers:
                # choose a random server
                current_analysis_id = random.choice(work_servers.keys())
                current_server = work_servers[current_analysis_id]

        work_socket = zmq_context.socket(zmq.REQ)
        try:
            work_socket.connect(current_server)
            # XXX - should send a quick "I'm here" message, then poll for a
            # reply, looping if we dont't get it.
        except:
            # give up on this server.  We'll get a new announcement if it comes back.
            with work_server_lock:
                del work_servers[current_analysis_id]
            continue

        try:
            # fetch a job
            job = WorkRequest().send(work_socket)
            if isinstance(job, ServerExited):
                continue  # server went away

            if isinstance(job, NoWorkReply):
                time.sleep(0.25)  # avoid hammering server
                # no work, currently.
                continue

            # Fetch the pipeline for this analysis if we don't have it
            current_pipeline = pipelines.get(current_analysis_id, None)
            if not current_pipeline:
                rep = PipelineRequest().send(work_socket)
                if isinstance(rep, ServerExited):
                    continue  # server went away
                pipeline_blob = rep.pipeline_blob
                pipeline = cpp.Pipeline()
                pipeline.loadtxt(StringIO.StringIO(pipeline_blob), raise_on_error=True)
                # make sure the server hasn't finished or quit since we fetched the pipeline
                with work_server_lock:
                    if current_analysis_id in work_servers:
                        current_pipeline = pipelines[current_analysis_id] = pipeline
                        pipeline.add_listener(pipeline_listener.handle_event)
                    else:
                        continue

            # point the pipeline event listener to the new work_socket
            pipeline_listener.work_socket = work_socket
            pipeline_listener.reset()

            # Fetch the path to the intial measurements if needed.
            # XXX - when implementing distributed workers, this will need to be
            # changed to actually fetch the measurements.
            current_measurements = initial_measurements.get(current_analysis_id, None)
            if current_measurements is None:
                rep = InitialMeasurementsRequest().send(work_socket)
                if isinstance(rep, ServerExited):
                    continue  # server went away
                measurements_path = rep.path.decode('utf-8')
                # make sure the server hasn't finished or quit since we fetched the pipeline
                with work_server_lock:
                    if current_analysis_id in work_servers:
                        current_measurements = \
                            initial_measurements[current_analysis_id] = \
                            cpmeas.load_measurements(measurements_path)
                    else:
                        continue

            def interaction_handler(module, *args, **kwargs):
                '''handle interaction requests by passing them to the jobserver and wait for the reply.'''
                # we write args and kwargs into the InteractionRequest to allow
                # more complex data to be sent by the underlying zmq machinery.
                arg_kwarg_dict = dict([('arg_%d' % idx, v) for idx, v in enumerate(args)] +
                                      [('kwarg_%s' % name, v) for (name, v) in kwargs.items()])
                req = InteractionRequest(module_num=module.module_num,
                                         num_args=len(args),
                                         kwargs_names=kwargs.keys(),
                                         **arg_kwarg_dict)
                rep = req.send(work_socket)
                if isinstance(rep, InteractionReply):
                    return rep.result
                elif isinstance(rep, ServerExited):
                    # the run was cancelled before we got a reply.
                    raise CancelledException()  # XXX - TODO - test this code path

            # Safest not to clobber measurements from one job to the next.
            current_measurements = cpmeas.Measurements(copy=current_measurements)
            successful_image_set_numbers = []
            image_set_numbers = job.image_set_numbers
            worker_runs_post_group = job.worker_runs_post_group
            print "Doing job: ", image_set_numbers

            pipeline_listener.image_set_number = image_set_numbers[0]

            # Get the shared state from the first imageset in this run.
            shared_dicts = SharedDictionaryRequest().send(work_socket).dictionaries
            assert len(shared_dicts) == len(current_pipeline.modules())
            for module, new_dict in zip(current_pipeline.modules(), shared_dicts):
                module.get_dictionary().clear()
                module.get_dictionary().update(new_dict)

            # Run prepare group if this is the first image in the group.  We do
            # this here (even if there's no grouping in the pipeline) to ensure
            # that any changes to the modules' shared state dictionaries get
            # propagated correctly.
            should_process = True
            if current_measurements[cpmeas.IMAGE, cpmeas.GROUP_INDEX, image_set_numbers[0]] == 1:
                workspace = cpw.Workspace(current_pipeline, None, None, None,
                                          current_measurements, None, None)
                # XXX - {} should be the grouping keys!
                if not current_pipeline.prepare_group(workspace, {}, image_set_numbers):
                    # exception handled elsewhere, possibly cancelling this run.
                    should_process = False

            # process the images
            if should_process:
                abort = False
                for image_set_number in image_set_numbers:
                    gc.collect()
                    try:
                        pipeline_listener.image_set_number = image_set_number
                        current_pipeline.run_image_set(current_measurements, image_set_number, interaction_handler)
                        if pipeline_listener.should_abort:
                            abort = True
                            break
                        elif pipeline_listener.should_skip:
                            # XXX - should we report skipped sets as "successful" in the sense of "done"?
                            # XXX - and should we report their measurements?
                            continue
                        successful_image_set_numbers.append(image_set_number)
                        # Send an indication that the image set finished successfully.
                        rep = ImageSetSuccess(image_set_number=image_set_number).send(work_socket)
                        if isinstance(rep, DictionaryReqRep):
                            # The jobserver would like a copy of our modules' run_state dictionaries.
                            # We use a nonstandard Req/rep/rep/rep pattern.
                            ws = cpw.Workspace(current_pipeline, None, None, None,
                                               current_measurements, None, None)
                            dicts = [m.get_dictionary(ws) for m in current_pipeline.modules()]
                            rep = rep.reply(DictionaryReqRepRep(shared_dicts=dicts), please_reply=True)
                        assert isinstance(rep, Ack)
                    except Exception:
                        try:
                            logging.error("Error in pipeline", exc_info=True)
                            if handle_exception(work_socket, image_set_number=image_set_number) == ED_STOP:
                                abort = True
                                break
                        except:
                            logging.error("Error in handling of pipeline exception", exc_info=True)
                            # this is bad.  We can't handle nested exceptions
                            # remotely so we just fail on this run.
                            abort = True

                if abort:
                    work_socket.close()
                    del current_measurements
                    current_measurements = None
                    continue

                if worker_runs_post_group:
                    workspace = cpw.Workspace(current_pipeline, None, None, None,
                                              current_measurements, None, None)
                    # There might be an exception in this call, but it will be
                    # handled elsewhere, and there's nothing we can do for it
                    # here.
                    current_pipeline.post_group(workspace, current_measurements.get_grouping_keys(), image_set_numbers)

            # multiprocessing: send path of measurements.
            # XXX - distributed - package them up.
            current_measurements.flush()
            req = MeasurementsReport(path=current_measurements.hdf5_dict.filename.encode('utf-8'),
                                     image_set_numbers=",".join(str(isn) for isn in successful_image_set_numbers))
            rep = req.send(work_socket)
            if isinstance(rep, ServerExited):
                continue  # server went away
            # rep is just an ACK
            work_socket.close()
            del current_measurements
        except Exception:
            logging.error("Error in worker", exc_info=True)
            # XXX - should we jsut assume complete failure and exit?
            if handle_exception(work_socket) == ED_STOP:
                # XXX - This should be an exit, yes?
                break


def handle_exception(work_socket, image_set_number=None, module_name=None, exc_info=None):
    '''report and handle an exception, possibly by remote debugging, returning
    how to proceed (skip or abort).
    '''
    if exc_info is None:
        t, exc, tb = sys.exc_info()
    else:
        t, exc, tb = exc_info
    filename, line_number, _, _ = traceback.extract_tb(tb, 1)[0]
    if image_set_number is not None:
        message = ["EXCEPTION", "PIPELINE", str(image_set_number), module_name,
                   t.__name__, str(exc), "".join(traceback.format_exception(t, exc, tb)),
                   filename, str(line_number)]
    else:
        message = ["EXCEPTION", "WORKER", t.__name__, str(exc),
                   "".join(traceback.format_exception(t, exc, tb)), filename, str(line_number)]
    work_socket.send_multipart(message)
    reply = work_socket.recv_multipart()
    while True:
        if reply[0] == 'DEBUG':
            def pc(port):
                work_socket.send_multipart(["DEBUG WAITING", str(port)])
            rpdb = Rpdb(verification_hash=reply[1], port_callback=pc)
            work_socket.recv()  # ACK
            rpdb.verify()
            rpdb.post_mortem(tb)
            work_socket.send_multipart(["DEBUG COMPLETE"])
            reply = work_socket.recv()  # next step (could be "DEBUG" again)
        else:
            return reply[0]


class PipelineEventListener(object):
    """listen for pipeline events, communicate them as necessary to the
    analysis manager."""
    def __init__(self):
        self.work_socket = None
        self.image_set_number = 0
        self.should_abort = False
        self.should_skip = False

    def reset(self):
        self.should_abort = False
        self.should_skip = False

    def handle_event(self, pipeline, event):
        if isinstance(event, cpp.RunExceptionEvent):
            disposition = handle_exception(self.work_socket,
                                           image_set_number=self.image_set_number,
                                           module_name=event.module.module_name,
                                           exc_info=(type(event), event, event.tb))
            if disposition == ED_STOP:
                self.should_abort = True
                event.cancel_run = True
            elif disposition == ED_SKIP:
                self.should_skip = True
                event.skip_thisset = True


def exit_on_stdin_close():
    '''Read until EOF, then exit, possibly without cleanup.'''
    # If sys.stdin closes, either our parent has closed it (indicating we
    # should exit), or our parent has died.  Attempt to exit cleanly via main
    # thread, but if that takes too long (hung filesystem or socket, perhaps),
    # use a hard os._exit() instead.
    stdin = sys.stdin
    try:
        while stdin.read():
            pass
    except:
        pass
    finally:
        thread.interrupt_main()  # try a soft shutdown
        # hard exit after 10 seconds
        time.sleep(10)
        os._exit(0)


def listen_for_announcements(work_announce_address,
                             work_servers, pipelines, initial_measurements,
                             work_server_lock):
    zmq_context = zmq.Context()
    work_announce_socket = zmq_context.socket(zmq.SUB)
    work_announce_socket.setsockopt(zmq.SUBSCRIBE, '')
    work_announce_socket.connect(work_announce_address)

    while True:
        work_queue_address, analysis_id = work_announce_socket.recv_multipart()
        with work_server_lock:
            if work_queue_address == 'DONE':
                # remove this work server
                if analysis_id in work_servers:
                    del work_servers[analysis_id]
                if analysis_id in pipelines:
                    del pipelines[analysis_id]
                if analysis_id in initial_measurements:
                    del initial_measurements[analysis_id]
            else:
                work_servers[analysis_id] = work_queue_address


def start_daemon_thread(target=None, args=(), name=None):
    thread = threading.Thread(target=target, args=args, name=name)
    thread.daemon = True
    thread.start()


class CancelledException(Exception):
    pass

def setup_callbacks(pipeline, work_socket):
    def post_module_callback(pipeline, module):
        # XXX - handle display
        work_socket.send_multipart(["POST_MODULE", module.module_name, str(module.module_number)])
        work_socket.recv_multipart()  # empty acknowledgement

    def exception_callback(event):
        if isinstance(event, pipeline.RunExceptionEvent):
            # XXX
            # report error back to main process
            # offer to PDB it
            # invoke PDB
            # Also need option to skip this set, continue pipeline, or cancel run.
            event.cancel_run = True

    pipeline.post_module_callback = post_module_callback
    pipeline.interaction_callback = interaction_callback
    pipeline.exception_callback = exception_callback
    # XXX - set up listener on pipeline for Events of all kinds


if __name__ == "__main__":
    import cellprofiler.preferences
    import sys
    sys.modules['cellprofiler.utilities.jutil'] = None
    cellprofiler.preferences.set_headless()
    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(logging.StreamHandler())
    main()