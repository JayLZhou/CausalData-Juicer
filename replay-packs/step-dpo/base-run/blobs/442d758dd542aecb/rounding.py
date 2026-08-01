import numpy as np

from checks import UNBOUNDED


def round2(values):
    return np.round_(np.array(values), 2).tolist()


def clip_upper(values, bound=UNBOUNDED):
    return np.minimum(np.array(values), bound).tolist()
