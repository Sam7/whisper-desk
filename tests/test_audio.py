import numpy as np
from whisper_desk.audio import AudioBuffer


def test_snapshot_absolute_positions_and_pruning():
    buffer = AudioBuffer(rate=10)
    buffer.append(np.arange(10))
    buffer.append(np.arange(10, 20))
    np.testing.assert_array_equal(buffer.snapshot(0.5, 1.5), np.arange(5, 15))
    buffer.prune(1.0)
    assert buffer.end == 2.0
    np.testing.assert_array_equal(buffer.snapshot(1.2), np.arange(12, 20))
    assert buffer.first_capture is not None


def test_capture_owns_its_memory():
    buffer = AudioBuffer()
    audio = np.ones(320, np.float32)
    buffer.append(audio)
    audio[:] = 0
    assert buffer.snapshot().sum() == 320


def test_buffer_backpressure_reports_error_without_growing():
    buffer = AudioBuffer(rate=10, max_seconds=1)
    buffer.append(np.ones(10))
    buffer.append(np.ones(10))
    assert buffer.error and buffer.end == 1
    assert len(buffer.snapshot()) == 10


def test_empty_snapshot_and_level():
    buffer = AudioBuffer()
    assert len(buffer.snapshot()) == 0
    buffer.append(np.full(320, 0.5))
    assert buffer.level == 0.5


def test_oversized_first_block_is_rejected():
    buffer = AudioBuffer(rate=10, max_seconds=1)
    buffer.append(np.ones(11))
    assert buffer.error and buffer.end == 0


def test_pruning_inside_a_block_releases_old_samples():
    buffer = AudioBuffer(rate=10)
    buffer.append(np.arange(100))
    buffer.prune(8)
    np.testing.assert_array_equal(buffer.snapshot(), np.arange(80, 100))
