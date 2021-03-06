from __future__ import print_function, division

import unittest
import tempfile
import time
import datetime
import os
import logging

# Disable log output for now
logging.disable(logging.CRITICAL)

import numpy as np
from numpy.testing import assert_almost_equal, assert_equal, assert_array_less

from rsimusim.simulation import RollingShutterImuSimulation, SimulationResults, transform_trajectory
from rsimusim.inertial import DefaultIMU
from crisp.camera import AtanCameraModel
from rsimusim.camera import PinholeModel

from .helpers import assert_timeseries_equal, random_orientation, random_position

EXAMPLE_SIMULATION_CONFIG = 'data/config_default.yml'

class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.sim = RollingShutterImuSimulation.from_config(EXAMPLE_SIMULATION_CONFIG, datasetdir='data/')
        self.tempfiles = []

    def tearDown(self):
        for fname in self.tempfiles:
            os.unlink(fname)

    def assert_image_obs_equal(self, im1, im2):
        assert_equal(im1.timestamps, im2.timestamps)
        for obs1, obs2 in zip(im1.values, im2.values):
            self.assertEqual(sorted(obs1.keys()), sorted(obs2.keys()))
            for key in obs1:
                ip1 = obs1[key]
                ip2 = obs2[key]
                assert_equal(ip1, ip2)

    def assert_image_obs_almost_equal(self, im1, im2, max_distance=1.0):
        assert_equal(im1.timestamps, im2.timestamps)
        for obs1, obs2 in zip(im1.values, im2.values):
            self.assertEqual(sorted(obs1.keys()), sorted(obs2.keys()))
            for key in obs1:
                ip1 = obs1[key]
                ip2 = obs2[key]
                d = np.linalg.norm(ip1 - ip2)
                print(d)
                self.assertLessEqual(d, max_distance)

    def get_temp(self):
        self.tempfiles.append(tempfile.mkstemp(prefix='simtests_')[1])
        return self.tempfiles[-1]

    def test_load_atan_camera(self):
        camera_model = self.sim.config.camera_model
        self.assertEqual(camera_model.__class__, AtanCameraModel)
        self.assertEqual(camera_model.columns, 1920)
        self.assertEqual(camera_model.rows, 1080)
        assert_almost_equal(camera_model.frame_rate, 30.0)
        expected_K = np.array([[ 853.12703455,    0.        ,  988.06311256],
                               [   0.        ,  873.54956631,  525.71056312],
                               [   0.        ,    0.        ,    1.        ]])
        assert_almost_equal(camera_model.camera_matrix, expected_K, decimal=3)
        assert_almost_equal(camera_model.wc, [ 0.00291108,  0.00041897], decimal=3)
        assert_almost_equal(camera_model.lgamma, 0.88943551779681562, decimal=3)
        assert_almost_equal(camera_model.readout, 0.031673400000000004, decimal=3)

    def test_load_pinhole_camera(self):
        sim = RollingShutterImuSimulation.from_config('data/config_pinhole.yml', datasetdir='data/')
        camera_model = sim.config.camera_model
        self.assertEqual(camera_model.__class__, PinholeModel)
        self.assertEqual(camera_model.columns, 1920)
        self.assertEqual(camera_model.rows, 1080)
        assert_almost_equal(camera_model.frame_rate, 30.0)
        expected_K = np.array([[ 853.12703455,    0.        ,  988.06311256],
                               [   0.        ,  873.54956631,  525.71056312],
                               [   0.        ,    0.        ,    1.        ]])
        assert_almost_equal(camera_model.K, expected_K, decimal=3)
        assert_almost_equal(camera_model.readout, 0.031673400000000004, decimal=3)

    def test_load_relative_pose(self):
        expected_R = np.array([[ 0.13275685,  0.13732874,  0.98158873],
                               [-0.70847681, -0.67943167,  0.19087489],
                               [ 0.69313508, -0.7207728 ,  0.00709502]])
        expected_p = np.array([0.1, -0.12, 0.03]).reshape(3,1)
        assert_almost_equal(self.sim.config.Rci, expected_R)
        assert_almost_equal(self.sim.config.pci, expected_p)

    def test_transformed_trajectory(self):
        R = np.array(random_orientation().toMatrix())
        p = random_position().reshape(3,1)

        ds = self.sim.config.dataset
        old_traj = ds.trajectory
        new_traj = transform_trajectory(old_traj, R, p)

        self.assertEqual(old_traj.startTime, new_traj.startTime)
        self.assertEqual(old_traj.endTime, new_traj.endTime)

        num_tested = 0
        for t in np.linspace(5.3, 6.6, num=20):
            landmarks = ds.visible_landmarks(t)
            print(len(landmarks), 'visible at time', t)
            R1 = np.array(old_traj.rotation(t).toMatrix())
            p1 = old_traj.position(t).reshape(3,1)
            R2 = np.array(new_traj.rotation(t).toMatrix())
            p2 = new_traj.position(t).reshape(3,1)
            for lm in landmarks:
                X = lm.position.reshape(3,1)
                X1 = R1.T @ (X - p1)
                X2 = R2.T @ (X - p2)
                X1_hat = R @ X2 + p
                assert_almost_equal(X1_hat, X1, decimal=2)
                num_tested += 1

        self.assertGreaterEqual(num_tested, 30)

    def test_relative_pose_projection(self):
        sim_rel = RollingShutterImuSimulation.from_config('data/config_withrelpose.yml', datasetdir='data/')
        sim_zero = RollingShutterImuSimulation.from_config('data/config_norelpose.yml', datasetdir='data/')

        result_rel = sim_rel.run()
        result_zero = sim_zero.run()

        self.assert_image_obs_almost_equal(result_rel.image_measurements,
                                           result_zero.image_measurements,
                                           max_distance=0.6)

    def test_faulty_rotation(self):
        with self.assertRaises(ValueError):
            sim = RollingShutterImuSimulation.from_config('data/config_bad_rotation.yml', datasetdir='data/')

    def test_load_dataset(self):
        self.assertEqual(self.sim.config.dataset.name, "example_walk")
        expected_start = 5.0
        expected_end = 7.0
        assert_almost_equal(self.sim.config.start_time, expected_start)
        assert_almost_equal(self.sim.config.end_time, expected_end)

    def test_load_dataset_wrong_time(self):
        with self.assertRaises(ValueError):
            sim = RollingShutterImuSimulation.from_config('data/config_bad_time.yml', datasetdir='data/')

    def test_load_dataset_notime(self):
        sim = RollingShutterImuSimulation.from_config('data/config_notime.yml', datasetdir='data/')
        expected_start = 0.93701929507460235
        expected_end = 29.028984602284506
        assert_almost_equal(sim.config.start_time, expected_start)
        assert_almost_equal(sim.config.end_time, expected_end)

    def test_load_dataset_not_aligned(self):
        with self.assertRaises(ValueError):
            sim = RollingShutterImuSimulation.from_config('data/config_notaligned.yml', datasetdir='data/')

    def test_load_imu_config(self):
        imu_config = self.sim.config.imu_config
        assert_almost_equal(imu_config['sample_rate'], 300.)
        expected_acc_noise = np.array([0.01, 0.002, 1.345e-5]).reshape(3,1)
        expected_acc_bias = np.array([-0.23, 0.05, 0.001]).reshape(3,1)
        assert_almost_equal(imu_config['accelerometer']['noise'], expected_acc_noise)
        assert_almost_equal(imu_config['accelerometer']['bias'], expected_acc_bias)
        expected_gyro_noise = 2.67e-5
        expected_gyro_bias = np.array([-0.9, 0.1, 0.031]).reshape(3,1)
        assert_almost_equal(imu_config['gyroscope']['noise'], expected_gyro_noise)
        assert_almost_equal(imu_config['gyroscope']['bias'], expected_gyro_bias)

    def test_load_imu(self):
        self.assertEqual(self.sim.imu.__class__, DefaultIMU)

    def test_run_simulation(self):
        t0 = datetime.datetime.now()
        results = self.sim.run()
        t1 = datetime.datetime.now()
        self.assertLess((results.time_started - t0).total_seconds(), 0.1)
        self.assertLess((t1 - results.time_finished).total_seconds(), 0.1)

        self.assertEqual(results.config_text, open(EXAMPLE_SIMULATION_CONFIG).read())
        self.assertEqual(results.config_path, EXAMPLE_SIMULATION_CONFIG)
        self.assertEqual(results.dataset_path, 'data/example_dataset.h5')

        image_ts = results.image_measurements
        gyro_ts = results.gyroscope_measurements
        acc_ts = results.accelerometer_measurements

        self.assertLess(image_ts.timestamps[0] - self.sim.config.start_time, 1. / self.sim.config.camera_model.frame_rate)
        assert_almost_equal(acc_ts.timestamps[0] - self.sim.config.start_time, 1. / self.sim.config.imu_config['sample_rate'])
        assert_almost_equal(gyro_ts.timestamps[0] - self.sim.config.start_time, 1. / self.sim.config.imu_config['sample_rate'])

        expected_duration = self.sim.config.end_time - self.sim.config.start_time
        image_duration = image_ts.timestamps[-1] - image_ts.timestamps[0]
        gyro_duration = gyro_ts.timestamps[-1] - gyro_ts.timestamps[0]
        acc_duration = acc_ts.timestamps[-1] - acc_ts.timestamps[0]

        expected_image_samples = int(image_duration * 30.0)
        expected_imu_samples = int(gyro_duration * 300.0)
        self.assertAlmostEqual(len(image_ts), expected_image_samples, delta=1.0)
        self.assertAlmostEqual(len(gyro_ts), expected_imu_samples, delta=3.0)

        last_camera_time = self.sim.config.end_time - self.sim.config.camera_model.readout
        assert_array_less(image_ts.timestamps, last_camera_time)

        # Expected max error is double the time delta because of the subtraction
        eps = 1e-6
        self.assertLess(np.abs(image_duration - expected_duration), 2. / self.sim.config.camera_model.frame_rate + eps)
        self.assertLess(np.abs(gyro_duration - expected_duration), 2. / self.sim.config.imu_config['sample_rate'] + eps)
        self.assertLess(np.abs(acc_duration - expected_duration), 2. / self.sim.config.imu_config['sample_rate'] + eps)
        assert_almost_equal(acc_ts.timestamps, gyro_ts.timestamps)

    def test_save_simulation(self):
        result = self.sim.run()
        fname = self.get_temp()
        result.save(fname)

        # Load from saved file and test if same values
        loaded = SimulationResults.from_file(fname)
        self.assertEqual(loaded.time_started, result.time_started)
        self.assertEqual(loaded.time_finished, result.time_finished)
        self.assertEqual(loaded.config_text, result.config_text)
        self.assertEqual(loaded.config_path, result.config_path)
        self.assertEqual(loaded.dataset_path, result.dataset_path)
        assert_timeseries_equal(loaded.gyroscope_measurements, result.gyroscope_measurements)
        assert_timeseries_equal(loaded.accelerometer_measurements, result.accelerometer_measurements)
        assert_timeseries_equal(loaded.trajectory.rotationKeyFrames, result.trajectory.rotationKeyFrames)
        assert_timeseries_equal(loaded.trajectory.positionKeyFrames, result.trajectory.positionKeyFrames)
        test_times = np.random.uniform(loaded.trajectory.startTime, loaded.trajectory.endTime, size=100)
        loaded_pos = loaded.trajectory.position(test_times)
        result_pos = result.trajectory.position(test_times)
        loaded_rot = loaded.trajectory.rotation(test_times)
        result_rot = loaded.trajectory.rotation(test_times)
        assert_almost_equal(loaded_pos, result_pos)
        assert_almost_equal(loaded_rot.array, result_rot.array)

        self.assert_image_obs_equal(loaded.image_measurements, result.image_measurements)

