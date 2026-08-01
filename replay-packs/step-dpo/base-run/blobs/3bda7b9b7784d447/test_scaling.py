import math

from scaling import scale_readings


def test_values_stay_finite():
    out = scale_readings([1.5, 2.0])
    assert all(math.isfinite(v) for v in out)
    assert out[0] == 1.5e39
