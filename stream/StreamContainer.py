from contextlib import contextmanager

import av
import streamlink


class StreamContainer:

    @staticmethod
    def get_container(url):
        streams = streamlink.streams(url)
        if "best" not in streams:
            raise Exception("No suitable stream found.")
        stream_obj = streams["best"]
        raw_stream = stream_obj.open()

        class StreamWrapper:
            def read(self, size=-1):
                return raw_stream.read(size)

            def readable(self):
                return True

        wrapped = StreamWrapper()
        container = av.open(wrapped)
        return container

    @staticmethod
    @contextmanager
    def get_container_context(url):
        container = StreamContainer.get_container(url)
        try:
            yield container
        finally:
            container.close()