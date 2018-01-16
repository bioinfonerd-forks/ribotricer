from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import pickle
import numpy as np
import pandas as pd
from mtspec import mtspec, mt_coherence
import six

def _shift_bit_length(x):
    """Shift bit"""
    return 1 << (x - 1).bit_length()


def _padwithzeros(vector, pad_width, iaxis, kwargs):
    """Pad with zeros"""
    vector[:pad_width[0]] = 0
    vector[-pad_width[1]:] = 0
    return vector


def get_periodicity(values, input_is_stream=False):
    """Calculate periodicty wrt 1-0-0 signal.

    Parameters
    ----------
    values : array like
             List of values
    Returns
    -------
    periodicity : float
                  Periodicity calculated as cross
                  correlation between input and idea 1-0-0 signal
    """
    tbp = 4
    kspec = 3
    nf = 30
    p = 0.90
    if input_is_stream:
        values = list(map(lambda x: float(x.rstrip()), values))
    if isinstance(values, six.string_types):
        try:
            values = pickle.load(open(values))
        except KeyError:
            pass
    values = pd.Series(values)
    values = values[0:max(values.index)]
    length = len(values)
    next_pow2_length = _shift_bit_length(length)
    values = np.lib.pad(values,
                        (0, next_pow2_length - len(values) % next_pow2_length),
                        _padwithzeros)
    mean_centered_values = values - np.nanmean(values)
    normalized_values = mean_centered_values / \
        np.max(np.abs(mean_centered_values))
    uniform_signal = [1, -0.6, -0.4] * (next_pow2_length // 3)
    uniform_signal = np.lib.pad(
        uniform_signal,
        (0, next_pow2_length - len(uniform_signal) % next_pow2_length),
        _padwithzeros)
    out = mt_coherence(
        1,
        normalized_values,
        uniform_signal,
        tbp,
        kspec,
        nf,
        p,
        freq=True,
        phase=True,
        cohe=True,
        iadapt=1)
    spec, freq, jackknife, fstatistics, _ = mtspec(
        data=values,
        delta=1.,
        time_bandwidth=4,
        number_of_tapers=3,
        statistics=True,
        rshape=0,
        fcrit=0.9)
    p = 99
    base_fstat = np.percentile(fstatistics, p)
    fstat = fstatistics[np.argmin(np.abs(freq - 1 / 3.0))]
    p_value = 'p < 0.05'
    if fstat < base_fstat:
        p_value = 'p > 0.05'
    return out['cohe'][np.argmin(np.abs(out['freq'] - 1 / 3.0))], p_value