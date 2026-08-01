import numpy as np


def compound(factors):
    return np.cumproduct(np.array(factors)).tolist()
