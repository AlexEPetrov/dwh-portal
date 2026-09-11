from queue import Queue

from proto import curve_data_service_pb2 as pb2
from proto.simulation_streamer import _ChunkIterator


def test_simulation_stream_ends_immediately_after_completion_chunk() -> None:
    queue: Queue = Queue()
    completion = pb2.SimulationDataChunk(
        request_id="request-1",
        simulations=[],
        metadata={"eof": "true"},
    )
    queue.put(completion)
    queue.put(None)

    iterator = _ChunkIterator(queue, "request-1")

    assert next(iterator) is completion
    try:
        next(iterator)
    except StopIteration:
        pass
    else:
        raise AssertionError("completion sentinel must close the request iterator")
