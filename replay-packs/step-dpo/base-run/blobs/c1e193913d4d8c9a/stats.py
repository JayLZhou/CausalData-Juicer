import numpy as np


def to_float_array(values):
    return np.array(values, dtype=np.float_)


def fill_missing(values):
    arr = to_float_array(values)
    arr[np.isnan(arr)] = 0.0
    return arr.tolist()


MISSING = np.NaN
