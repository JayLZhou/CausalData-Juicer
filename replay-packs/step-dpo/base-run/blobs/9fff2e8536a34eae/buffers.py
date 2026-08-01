import numpy as np


def as_row(values):
    return np.array(values, dtype=np.float64, copy=True).reshape(1, -1)


def stack_rows(rows):
    mats = [np.array(r, dtype=np.float64, copy=True) for r in rows]
    return np.vstack(mats)