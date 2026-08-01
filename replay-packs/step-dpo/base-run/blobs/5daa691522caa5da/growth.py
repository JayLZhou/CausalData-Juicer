import numpy as np


def compound(factors):
    return np.cumprod(np.array(factors)).tolist()