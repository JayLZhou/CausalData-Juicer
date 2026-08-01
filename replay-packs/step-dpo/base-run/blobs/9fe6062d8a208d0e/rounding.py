import numpy as np
from checks import UNBOUNDED


def round2(values):
    return [round(value, 2) for value in values]

def clip_upper(values, bound=UNBOUNDED):
    return np.minimum(np.array(values), bound).tolist()
