"""Ciclo de vida completo com áudio e STT simulados, sem hardware."""

import asyncio
import threading
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from agy_voice.interfaces import STTStrategy, TranscriptionSegment
from ataflow.recording.session import SessionManager


class FakeCapture:
    sample_rate = 10

    def __init__(self):
        self.mic_queue = asyncio.Queue()
        self.sys_queue = asyncio.Queue()
        self.stop_calls = 0
        self.final_audio = None
        self.final_queue = self.sys_queue

    def start(self, *, mic_index, sys_index, loop):
        self.loop = loop

    def stop(self):
        self.stop_calls += 1
        if self.final_audio is not None:
            self.loop.call_soon_threadsafe(self.final_queue.put_nowait, self.final_audio)


class FakeSTT(STTStrategy):
    @property
    def sample_rate(self):
        return 10

    def is_available(self):
        return True

    def __init__(self):
        self.audio = []

    def load(self):
        return True

    def transcribe(self, audio):
        self.audio.append(audio.copy())
        return [TranscriptionSegment(0, len(audio) / self.sample_rate, f"bloco-{len(self.audio)}")]


@pytest.fixture
def session(tmp_path):
    return SessionManager(
        chunk_duration=1,
        overlap=0.2,
        max_queue_size=1,
        stt=FakeSTT(),
        audio_capture=FakeCapture(),
        output_dir=tmp_path,
    )


@pytest.mark.parametrize("channel", ["mic_queue", "sys_queue"])
async def test_finish_flushes_short_recording_and_last_callback(session, channel):
    await session.start()
    audio = np.arange(4, dtype=np.float32) / 100
    getattr(session.audio_capture, channel).put_nowait(audio)
    session.audio_capture.final_audio = np.zeros(4, dtype=np.float32)
    if channel == "sys_queue":
        session.audio_capture.final_queue = session.audio_capture.mic_queue
    output = await asyncio.wait_for(session.finish(), 3)
    assert session.finished and not session.running
    assert len(session.stt.audio) == 1
    np.testing.assert_array_equal(session.stt.audio[0], audio)
    assert "bloco-1" in Path(output).read_text(encoding="utf-8")
    assert session.session_events.get_nowait()["type"] == "transcription"


@pytest.mark.parametrize(
    "length, expected_lengths", [(10, [10]), (12, [10, 4]), (34, [10, 10, 10, 10])]
)
async def test_drains_backlog_without_dropping_or_repeating_overlap(
    session, length, expected_lengths
):
    await session.start()
    audio = np.arange(length, dtype=np.float32) / 100
    session.audio_capture.mic_queue.put_nowait(audio)
    await asyncio.wait_for(session.finish(), 3)
    assert [len(chunk) for chunk in session.stt.audio] == expected_lengths
    for index, chunk in enumerate(session.stt.audio):
        np.testing.assert_array_equal(chunk, audio[index * 8 : index * 8 + len(chunk)])
    assert Path(session.output_file).read_text(encoding="utf-8").count("bloco-") == len(
        expected_lengths
    )
    await asyncio.wait_for(session._transcription_queue.join(), 1)


async def test_finish_waits_for_inflight_transcription_and_is_idempotent(session):
    entered = asyncio.Event()
    release = threading.Event()
    original = session.stt.transcribe
    loop = asyncio.get_running_loop()

    def slow_transcribe(audio):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return original(audio)

    session.stt.transcribe = slow_transcribe
    await session.start()
    session.audio_capture.mic_queue.put_nowait(np.zeros(10, dtype=np.float32))
    await asyncio.wait_for(entered.wait(), 2)
    closing = asyncio.create_task(session.finish())
    try:
        await asyncio.sleep(0.05)
        assert not closing.done()
        assert not Path(session.output_file).exists()
    finally:
        release.set()
    output = await asyncio.wait_for(closing, 3)
    assert "bloco-1" in Path(output).read_text(encoding="utf-8")
    assert await session.finish() == output
    assert session.audio_capture.stop_calls == 1
    assert session._processing_task.done()


@pytest.mark.parametrize("failure", ["transcribe", "write"])
async def test_processing_error_blocks_success_and_stops_capture(session, monkeypatch, failure):
    if failure == "transcribe":
        session.stt.transcribe = Mock(side_effect=RuntimeError("STT indisponível"))
    else:
        monkeypatch.setattr(session, "_save_line", Mock(side_effect=OSError("Disco cheio")))
    await session.start()
    session.audio_capture.mic_queue.put_nowait(np.zeros(30, dtype=np.float32))
    with pytest.raises(RuntimeError, match="Não foi possível concluir"):
        await asyncio.wait_for(session.finish(), 3)
    assert session.finished and not session.running
    assert session.audio_capture.stop_calls == 1
    assert session._processing_task.done()
    assert session.session_events.get_nowait()["type"] == "error"


async def test_failure_during_live_processing_closes_capture(session):
    session.stt.transcribe = Mock(side_effect=RuntimeError("Falha"))
    await session.start()
    session.audio_capture.mic_queue.put_nowait(np.zeros(30, dtype=np.float32))
    await asyncio.wait_for(session._finished.wait(), 3)
    assert session.audio_capture.stop_calls == 1
    with pytest.raises(RuntimeError):
        await session.finish()


async def test_failed_load_cleans_up_without_starting_pipeline(session):
    session.stt.load = lambda: False
    assert not await session.start()
    assert session.finished
    assert session._processing_task is None
    assert session.audio_capture.stop_calls == 1


async def test_capture_start_failure_cleans_up(session):
    session.audio_capture.start = Mock(side_effect=OSError("Dispositivo desconectado"))
    with pytest.raises(OSError):
        await session.start()
    assert session.finished and not session.running
    assert session.audio_capture.stop_calls == 1


async def test_overlaps_are_removed_for_any_stt_strategy(session):
    texts = iter(["a decisão foi aprovada", "a decisão foi aprovada", "aprovada por todos"])

    def transcribe(audio):
        return [TranscriptionSegment(0, 1, next(texts))]

    session.stt.transcribe = transcribe
    await session.start()
    session.audio_capture.mic_queue.put_nowait(np.zeros(26, dtype=np.float32))
    await session.finish()
    saved = Path(session.output_file).read_text(encoding="utf-8")
    assert saved.count("a decisão foi aprovada") == 1
    assert saved.count("aprovada") == 1
    assert "por todos" in saved


async def test_whisper_failure_is_not_treated_as_silence(session):
    from agy_voice.stt import WhisperLocalSTT

    stt = WhisperLocalSTT()
    stt._model = Mock()
    stt._model.transcribe.side_effect = RuntimeError("Falha da GPU")
    stt.load = lambda: True
    session.stt = stt
    await session.start()
    session.audio_capture.mic_queue.put_nowait(np.zeros(10, dtype=np.float32))
    with pytest.raises(RuntimeError, match="Não foi possível concluir"):
        await session.finish()


@pytest.mark.parametrize(
    "seconds, expected", [(0, "00:00:00"), (65, "00:01:05"), (3665, "01:01:05")]
)
def test_format_time(seconds, expected):
    assert SessionManager._fmt_time(seconds) == expected


@pytest.mark.parametrize("chunk, overlap", [(0, 0), (1, 1), (1, -1)])
def test_invalid_chunk_settings(chunk, overlap):
    with pytest.raises(ValueError):
        SessionManager(chunk_duration=chunk, overlap=overlap, stt=FakeSTT())
