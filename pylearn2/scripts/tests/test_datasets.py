"""
Tests for all datasets scripts
"""

import numpy
import os
import shutil
import tempfile
from pylearn2.datasets import norb
from pylearn2.scripts.datasets import (make_cifar100_gcn_whitened,
                                       make_cifar100_patches,
                                       make_cifar100_patches_8x8,
                                       make_cifar100_whitened,
                                       make_cifar10_gcn_whitened,
                                       make_cifar10_whitened,
                                       make_downsampled_stl10,
                                       make_stl10_patches,
                                       make_stl10_patches_8x8,
                                       make_stl10_whitened,
                                       browse_small_norb)
from pylearn2.testing.datasets import ArangeDataset


def dataset_output(dataset_script):
    """
    Function to verify the creation of an output folder for a specific script

    Parameters
    ----------
    dataset_script : Python script
                     Preprocessing to apply on specific dataset.
    """
    try:
        data_dir = tempfile.mkdtemp()
        output_dir = dataset_script.create_output_dir(data_dir)

        assert os.path.exists(output_dir)
        assert os.path.exists(output_dir + '/README')

        fake_data = ArangeDataset(2)
        dataset_script.save_dataset(output_dir, fake_data, 'fake')

        assert os.path.exists(output_dir + '/fake.npy')
        assert os.path.exists(output_dir + '/fake.pkl')

    finally:
        shutil.rmtree(data_dir)


def test_cifar100_gcn_whitened_output():
    """Test output folder creation for cifar100 gcn whitened script"""
    dataset_output(make_cifar100_gcn_whitened)


def test_cifar100_patches_output():
    """Test output folder creation for cifar100 with patches script"""
    dataset_output(make_cifar100_patches)


def test_cifar100_patches_8x8_output():
    """Test output folder creation for cifar100 witch 8x8 patches script"""
    dataset_output(make_cifar100_patches_8x8)


def test_cifar100_whitened_output():
    """Test output folder creation for cifar100 whitened script"""
    dataset_output(make_cifar100_whitened)


def test_cifar10_gcn_whitened_output():
    """Test output folder creation for cifar10 gcn whitened script"""
    dataset_output(make_cifar10_gcn_whitened)


def test_cifar10_whitened_output():
    """Test output folder creation for cifar10 whitened script"""
    dataset_output(make_cifar10_whitened)


def test_stl10_downsampled_output():
    """Test output folder creation for stl10 downsampled script"""
    dataset_output(make_downsampled_stl10)


def test_stl10_patches_output():
    """Test output folder creation for stl10 with patches script"""
    dataset_output(make_stl10_patches)


def test_stl10_patches_8x8_output():
    """Test output folder creation for stl10 with 8x8 patches script"""
    dataset_output(make_stl10_patches_8x8)


def test_stl10_whitened_output():
    """Test output folder creation for stl10 whitened script"""
    dataset_output(make_stl10_whitened)


def test_small_norb_browser_remap():
    """Test if the remapping of label and instances is correct"""
    train_labels = numpy.array([[0, 8, 6, 4, 4], [0, 0, 0, 0, 0]], 'int')
    test_labels = numpy.array([[2, 5, 8, 34, 5], [0, 0, 0, 0, 0]], 'int')

    browser_train = browse_small_norb.SmallNorbBrowser(train_labels, 'train')
    browser_test = browse_small_norb.SmallNorbBrowser(test_labels, 'test')

    assert browser_train.labels[0, :].tolist() == [0, 3, 6, 2, 4]
    assert browser_train.new_to_old_instance == [4, 6, 7, 8, 9]
    assert browser_test.labels[0, :].tolist() == [2, 4, 8, 17, 5]
    assert browser_test.new_to_old_instance == [0, 1, 2, 3, 5]


def test_small_norb_browser_get_new_azimuth():
    """Test the get_new_azimuth_degrees method"""
    labels = numpy.asarray([[0, 8, 6, 4, 4], [0, 0, 0, 0, 0]])
    browser = browse_small_norb.SmallNorbBrowser(labels, 'train')

    assert browser.get_new_azimuth_degrees(4) == 80
