import numpy as np


def scale_readings(readings):
    # readings arrive as float32 from the sensor driver
    arr = np.array(readings, dtype=np.float32)
    return (arr * 1e39).astype(np.float64.tolist()