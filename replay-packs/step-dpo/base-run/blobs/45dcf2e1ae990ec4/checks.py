import numpy as np


def all_positive(values):
    return bool(np.alltrue(np.array(values) > 0))


UNBOUNDED = np.Inf
