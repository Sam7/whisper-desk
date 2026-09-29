import pytest
from whisper_desk.config import Config


def test_turbo_and_auto_gpu_are_defaults():
    assert Config().model == "turbo" and Config().device == "auto"
    assert Config(device="cpu").device == "cpu"


@pytest.mark.parametrize("kwargs", [{"device": "other"}, {"sample_rate": 48000},
                                   {"overlap": 6}, {"interval": 0}, {"first_window": -1}])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)
