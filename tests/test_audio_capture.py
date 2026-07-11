import numpy as np
from audio_capture import AudioCapture

def test_mix_and_normalize_no_clipping():
    mic = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    sys = np.array([0.2, 0.1, 0.0], dtype=np.float32)
    
    mixed = AudioCapture.mix_and_normalize(mic, sys)
    
    assert len(mixed) == 3
    assert np.allclose(mixed, [0.3, 0.3, 0.3])
    
def test_mix_and_normalize_with_clipping():
    mic = np.array([0.8, 0.9, -0.8], dtype=np.float32)
    sys = np.array([0.8, 0.2, -0.5], dtype=np.float32)
    
    # max value will be 1.6 at index 0. 
    # peak is 1.6
    # expected: [1.6/1.6, 1.1/1.6, -1.3/1.6] = [1.0, 0.6875, -0.8125]
    mixed = AudioCapture.mix_and_normalize(mic, sys)
    
    assert np.isclose(np.max(np.abs(mixed)), 1.0)
    assert np.isclose(mixed[0], 1.0)
    assert np.isclose(mixed[1], 1.1/1.6)
    assert np.isclose(mixed[2], -1.3/1.6)

def test_mix_different_lengths():
    mic = np.array([0.1, 0.1], dtype=np.float32)
    sys = np.array([0.2, 0.2, 0.2], dtype=np.float32)
    
    mixed = AudioCapture.mix_and_normalize(mic, sys)
    
    assert len(mixed) == 3
    assert np.allclose(mixed, [0.3, 0.3, 0.2])

