"""BrainVision RDA client from Leon-Parepko/EEG-Experiment-Script (branch eeg_image_reconst_local_ver, RDA_threaded.py).

The thread API is unchanged: run_rda_thread() / stop_thread().
The only local change is output_dir, so CSV files land in the session folder
instead of the working directory.
"""

import asyncio
import concurrent.futures
import json
import logging
import struct
import sys
import threading
import datetime

from asyncio import StreamReader, StreamWriter
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Self, TypeAlias
import aiofiles


Microseconds: TypeAlias = float


class MessageType(Enum):
    START = 1
    DATA16BIT = 2
    END = 3
    DATA = 4


@dataclass
class Marker:
    position: int
    points: int
    channel: int
    type_name: str
    description: str

    @classmethod
    def list_from_bytes(cls, raw_data: bytes, count: int) -> list[Self]:
        MIN_SIZE_OFFSET = 16  # four longs

        markers: list[Self] = []

        offset = 0
        for _ in range(count):
            length, position, points, channel = struct.unpack('<LLLl', raw_data[offset:offset + MIN_SIZE_OFFSET])
            type_name, description, *_ = raw_data[offset + MIN_SIZE_OFFSET:offset + length].split(b'\x00')
            
            markers.append(cls(position, points, channel, type_name, description))

            offset += length
        
        return markers
    
    @staticmethod
    def list_to_file_file_format(markers: list[Self], block_id: int) -> Generator[str, None, None]:
        for marker in markers:
            yield f'{block_id},{marker.position},{marker.points},{marker.channel},{marker.type_name.decode()},{marker.description.decode()};\n'


@dataclass
class DataBlock:
    block_id: int
    points: list[float]
    markers: list[Marker]

    @classmethod
    def from_bytes(cls, raw_data: bytes, channels_count: int) -> Self:
        MIN_SIZE_OFFSET = 12  # three unsigned longs
        FLOAT_SIZE = 4

        block_id, points_count, markers_count = struct.unpack('<LLL', raw_data[:MIN_SIZE_OFFSET])

        points_raw_string = raw_data[MIN_SIZE_OFFSET:MIN_SIZE_OFFSET + points_count * channels_count * FLOAT_SIZE]
        try:
            points = list(struct.unpack(f'<{"f" * points_count * channels_count}', points_raw_string))
        except Exception as ex:
            raise RuntimeError(
                f"RDA block {block_id} has {points_count} samples x {channels_count} channels, "
                f"{markers_count} markers, {len(points_raw_string)} data bytes"
            ) from ex

        if markers_count:
            markers_raw_string = raw_data[MIN_SIZE_OFFSET + points_count * channels_count * FLOAT_SIZE:]
            markers = Marker.list_from_bytes(markers_raw_string, markers_count)
        else:
            markers = []

        return cls(block_id, points, markers)
    
    def to_file_format(self, channels_count: int) -> Generator[str, None, None]:
        for i in range(0, len(self.points), channels_count):
            yield f'{self.block_id},{datetime.datetime.now().timestamp()},{",".join(map(str, self.points[i:i + channels_count]))};\n'


@dataclass
class HeaderPayload:
    guid: list[int]  # from docs: 128-bit constant for unique identification.
    message_length: int
    message_type: MessageType

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> Self:
        *guid, message_length, message_type = struct.unpack('<llllLL', raw_data)
        return cls(guid, message_length, message_type)


@dataclass
class PropertiesPayload:
    sampling_interval: Microseconds
    resolutions: tuple[float, ...]
    channel_names: tuple[str, ...]

    @classmethod
    def from_bytes(cls, raw_data: bytes) -> Self:
        MIN_SIZE_OFFSET = 12  # one unsigned long plus one double
        DOUBLE_SIZE = 8  # double as C type

        channels_count, sampling_interval = struct.unpack('<Ld', raw_data[:MIN_SIZE_OFFSET])

        resolutions_raw_string = raw_data[MIN_SIZE_OFFSET:MIN_SIZE_OFFSET + DOUBLE_SIZE * channels_count]
        resolutions = struct.unpack(f'<{"d" * channels_count}', resolutions_raw_string)

        channel_names = map(bytes.decode, raw_data[MIN_SIZE_OFFSET + DOUBLE_SIZE * channels_count:].split(b'\x00'))
        channel_names = tuple(filter(bool, channel_names))

        return cls(sampling_interval, resolutions, channel_names)


class FileWritter:
    def __init__(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        self.data_blocks_filename = output_dir / "datablocks.csv"
        self.properties_filename = output_dir / "properties.json"
        self.markers_filename = output_dir / "markers.csv"

        self.filenames: list[Path] = [
            self.data_blocks_filename,
            self.properties_filename,
            self.markers_filename,
        ]
        self.files: dict[Path, aiofiles.threadpool.binary.AsyncBufferedIOBase] = {}

        self.properties: PropertiesPayload | None = None
    
    async def __aenter__(self) -> Self:
        for filename in self.filenames:
            self.files[filename] = await aiofiles.open(filename, 'w')

        return self

    async def __aexit__(self, *args) -> None:
        for file in self.files.values():
            await file.close()
    
    async def write_data_block(self, data_block: DataBlock) -> None:
        for line in data_block.to_file_format(len(self.properties.channel_names)):
            await self.files[self.data_blocks_filename].write(line)
        await self.files[self.data_blocks_filename].flush()

        for line in Marker.list_to_file_file_format(data_block.markers, data_block.block_id):
            await self.files[self.markers_filename].write(line)
        if data_block.markers:
            await self.files[self.markers_filename].flush()
    
    async def write_properties(self, properties: PropertiesPayload) -> None:
        self.properties = properties
        await self.files[self.properties_filename].write(json.dumps(asdict(properties)))
        await self.files[self.properties_filename].flush()


class RDA:
    def __init__(
        self,
        host_ip: str,
        port: int,
        output_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ):
        self.host_ip = host_ip
        self.port = port
        self.output_dir = Path(output_dir) if output_dir is not None else Path('.')
        self._logger = logger or logging.getLogger("neuro_se.eeg")
        self.blocks_written = 0
        self.samples_written = 0
        self.markers_written = 0

        self.socket_reader: StreamReader | None = None
        self.socket_writer: StreamWriter | None = None

        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.receiver_future: asyncio.Future | None = None
        self._properties_ready = threading.Event()
        self._recording = threading.Event()
        self._receiver_done = threading.Event()
        self._failure: BaseException | None = None
    
    async def connect(self) -> None:
        self._logger.info("[EEG-RDA] socket %s:%s", self.host_ip, self.port)
        self.socket_reader, self.socket_writer = await asyncio.open_connection(self.host_ip, self.port)
        self._logger.info("[EEG-RDA] connected")
    
    async def disconnect(self) -> None:
        if self.socket_writer is None:
            return
        self.socket_writer.close()
        await self.socket_writer.wait_closed()
        self.socket_writer = None
    
    async def run_data_receiver(self) -> None:
        HEADER_SIZE = 24
        properties: PropertiesPayload | None = None
        keep_receiving = True

        try:
            await self.connect()
            async with FileWritter(self.output_dir) as file_writter:
                while keep_receiving:
                    header_raw: bytes = await self.socket_reader.readexactly(HEADER_SIZE)
                    header_payload = HeaderPayload.from_bytes(header_raw)

                    data_raw: bytes = await self.socket_reader.readexactly(
                        header_payload.message_length - HEADER_SIZE
                    )

                    match header_payload.message_type:
                        case 1:
                            properties = PropertiesPayload.from_bytes(data_raw)
                            await file_writter.write_properties(properties)
                            rate = 1_000_000.0 / properties.sampling_interval if properties.sampling_interval else 0
                            self._logger.info(
                                "[EEG-RDA] recorder: %.3f Hz, %d channels: %s",
                                rate,
                                len(properties.channel_names),
                                ", ".join(properties.channel_names),
                            )
                            self._logger.info(
                                "[EEG-RDA] files: %s | %s | %s",
                                file_writter.data_blocks_filename,
                                file_writter.properties_filename,
                                file_writter.markers_filename,
                            )
                            self._properties_ready.set()
                        case 4:
                            if properties is None:
                                self._logger.error("[EEG-RDA] data arrived before the channel header")
                                continue
                            data_block = DataBlock.from_bytes(data_raw, len(properties.channel_names))
                            if not self._recording.is_set():
                                continue
                            await file_writter.write_data_block(data_block)
                            channels = len(properties.channel_names) or 1
                            self.blocks_written += 1
                            self.samples_written += len(data_block.points) // channels
                            for marker in data_block.markers:
                                self.markers_written += 1
                                self._logger.info(
                                    "[EEG-RDA] marker block=%s pos=%s ch=%s type=%s text=%s",
                                    data_block.block_id,
                                    marker.position,
                                    marker.channel,
                                    marker.type_name.decode(errors="replace"),
                                    marker.description.decode(errors="replace"),
                                )
                            if self.blocks_written == 1 or self.blocks_written % 50 == 0:
                                self._logger.info(
                                    "[EEG-RDA] blocks=%d samples=%d markers=%d",
                                    self.blocks_written,
                                    self.samples_written,
                                    self.markers_written,
                                )
                        case 3:
                            self._logger.info("[EEG-RDA] recorder sent stop")
                            keep_receiving = False
                        case 10000:
                            continue
                        case _:
                            self._logger.warning(
                                "[EEG-RDA] unknown message type %s",
                                header_payload.message_type,
                            )
                            continue
                self._logger.info("[EEG-RDA] receiver finished")
                if properties is None:
                    self._failure = RuntimeError('RDA stopped before recorder properties arrived')
                    self._properties_ready.set()
        except asyncio.CancelledError:
            self._logger.info(
                "[EEG-RDA] stopped blocks=%d samples=%d markers=%d",
                self.blocks_written,
                self.samples_written,
                self.markers_written,
            )
            raise
        except Exception:
            self._failure = sys.exc_info()[1]
            self._properties_ready.set()
            self._logger.exception("[EEG-RDA] receiver failed")
            raise
        finally:
            try:
                await self.disconnect()
                self._logger.info("[EEG-RDA] socket closed")
            finally:
                self._receiver_done.set()
    
    def run_thread(self) -> None:
        def start_loop(loop: asyncio.AbstractEventLoop) -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=start_loop, args=(self.loop,), daemon=True)
        self.thread.start()

        self.receiver_future = asyncio.run_coroutine_threadsafe(self.run_data_receiver(), self.loop)

    def wait_until_ready(self, timeout: float = 5.0) -> None:
        """Wait until recorder properties arrive, propagating setup failures."""
        if not self._properties_ready.wait(timeout):
            raise TimeoutError(
                f'RDA {self.host_ip}:{self.port} did not send recorder properties '
                f'within {timeout:.0f} seconds'
            )
        if self._failure is not None:
            raise RuntimeError(
                f'RDA setup failed for {self.host_ip}:{self.port}: {self._failure}'
            ) from self._failure

    def begin_recording(self) -> None:
        """Retain blocks after Space, including when properties arrive later."""
        if self._failure is not None:
            raise RuntimeError(f'RDA receiver failed: {self._failure}') from self._failure
        self._recording.set()
        if self._properties_ready.is_set():
            self._logger.info('[EEG-RDA] recording enabled')
        else:
            self._logger.warning(
                '[EEG-RDA] recording armed in the background; '
                'waiting for recorder properties and data'
            )
    
    def stop_thread(self) -> None:
        if self.receiver_future:
            self.receiver_future.cancel()
            try:
                self.receiver_future.result()
            except (asyncio.CancelledError, concurrent.futures.CancelledError):
                pass
            except Exception:
                self._logger.exception("[EEG-RDA] receiver ended with an error")
            self._receiver_done.wait(timeout=5.0)
        
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.thread:
            self.thread.join(timeout=5.0)


def run_rda(host_ip: str = '100.1.1.3', port: int = 51244) -> None:
    rda = RDA(host_ip=host_ip, port=port)
    asyncio.run(rda.run_data_receiver())


def run_rda_thread(
    host_ip: str = '100.1.1.3',
    port: int = 51244,
    output_dir: Path | None = None,
    logger: logging.Logger | None = None,
):
    rda = RDA(host_ip=host_ip, port=port, output_dir=output_dir, logger=logger)
    rda.run_thread()
    return rda


if __name__ == '__main__':
    run_rda()
