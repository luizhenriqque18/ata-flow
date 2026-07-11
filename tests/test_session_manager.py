from session_manager import SessionManager
import os
from unittest.mock import patch

def test_session_manager_init():
    manager = SessionManager(chunk_duration=10.0, overlap=2.0)
    assert manager.chunk_duration == 10.0
    assert manager.overlap == 2.0
    assert manager.running is False
    assert os.path.exists(manager.output_dir)

@patch("session_manager.LocalTranscriber")
@patch("session_manager.AudioCapture")
def test_session_manager_format_time(mock_audio, mock_transcriber):
    manager = SessionManager()
    
    assert manager._format_time(0) == "00:00:00"
    assert manager._format_time(65) == "00:01:05"
    assert manager._format_time(3665) == "01:01:05"

