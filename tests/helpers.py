import numpy as np
from imusim.maths.quaternions import Quaternion, QuaternionArray
from numpy import testing as nt
from numpy.testing import assert_equal

from crisp.fastintegrate import integrate_gyro_quaternion_uniform

def random_position():
    return np.random.uniform(-10, 10, size=3)

def random_orientation():
    qdata = np.random.uniform(-2, 2, size=4)
    qdata /= np.linalg.norm(qdata)
    q = Quaternion(*qdata)
    return q


def random_focal():
    return np.random.uniform(100., 1000.)

def unpack_quat(q):
    return np.array([q.w, q.x, q.y, q.z])

def gyro_data_to_quaternion_array(gyro_data, gyro_times):
    dt = float(gyro_times[1] - gyro_times[0])
    nt.assert_almost_equal(np.diff(gyro_times), dt)
    q = integrate_gyro_quaternion_uniform(gyro_data, dt)
    return QuaternionArray(q)


def find_landmark(p, landmarks):
    if not landmarks:
        return None

    lm = next((lm for lm in landmarks if np.all(lm.position == p)), None)
    return lm

def assert_timeseries_equal(ts1, ts2):
    assert_equal(ts1.values, ts2.values)
    assert_equal(ts1.timestamps, ts2.timestamps)

#    best = min(landmarks, key=lambda lm: np.linalg.norm(lm.position - p))
#    if np.allclose(best.position, p):
#        return best
#    else:
#        return None
