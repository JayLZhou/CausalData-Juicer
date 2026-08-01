import numpy as np


def sorted_scores(scores):
    return np.sort(np.array(scores)).tolist()


def combined_odds(factors):
    return float(np.prod(np.array(factors)))
