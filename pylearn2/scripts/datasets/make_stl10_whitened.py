"""
This script makes a dataset of 32x32 approximately whitened STL-10 images.

It assumes that you have already run make_downsampled_stl10.py,
which downsamples the STL-10 images to 1/3 of their original resolution.

"""

from pylearn2.utils import serial
from pylearn2.datasets import preprocessing
from pylearn2.utils import string_utils as string
import numpy as np


def create_output_dir(data_dir):
    """
    Preparation of the directory.

    Parameters
    ----------
    data_dir: str
        Path of the stl10 directory.
    """
    output_dir = data_dir + '/stl10_32x32_whitened'
    serial.mkdir(output_dir)
    README = open(output_dir + '/README', 'w')

    README.write("""
    The .pkl files in this directory may be opened in python using
    cPickle, pickle, or pylearn2.serial.load.

    unsupervised.pkl, unlabeled.pkl, train.pkl, and test.pkl each contain
    a pylearn2 Dataset object defining an unlabeled
    dataset of a 32x32 approximately whitened version of the STL-10
    dataset. unlabeled.pkl contains unlabeled train examples. train.pkl
    contains labeled train examples. unsupervised.pkl contains the union
    of these (without any labels). test.pkl contains the labeled test
    examples.

    preprocessor.pkl contains a pylearn2 ZCA object that was used
    to approximately whiten the images. You may want to use this
    object later to preprocess other images.

    They were created with the pylearn2 script make_stl10_whitened.py.

    All other files in this directory, including this README, were
    created by the same script and are necessary for the other files
    to function correctly.
    """)

    README.close()

    return output_dir


def save_dataset(output_dir, dataset, name):
    """
    Save the newly created dataset to the given directory.

    Parameters
    ----------
    output_dir: str
        Path of the directory where to save the dataset.
    dataset: pylearn2.datasets.Dataset
        The dataset to save.
    name: str
        Name of the file to save.
    """
    dataset.use_design_loc(output_dir + '/' + name + '.npy')
    serial.save(output_dir + '/' + name + '.pkl', dataset)

if __name__ == '__main__':
    data_dir = string.preprocess('${PYLEARN2_DATA_PATH}/stl10')

    print 'Loading STL-10 unlabeled and train datasets...'
    downsampled_dir = data_dir + '/stl10_32x32'

    data = serial.load(downsampled_dir + '/unlabeled.pkl')
    supplement = serial.load(downsampled_dir + '/train.pkl')

    print 'Concatenating datasets...'
    data.set_design_matrix(np.concatenate((data.X, supplement.X), axis=0))

    print "Preparing output directory..."
    output_dir = create_output_dir(data_dir)

    print ("Learning the preprocessor and preprocessing "
           "the unsupervised train data...")
    preprocessor = preprocessing.ZCA()
    data.apply_preprocessor(preprocessor=preprocessor, can_fit=True)

    print 'Saving the unsupervised data'
    data.use_design_loc(output_dir+'/unsupervised.npy')
    serial.save(output_dir + '/unsupervised.pkl', data)

    X = data.X
    unlabeled = X[0:100*1000, :]
    labeled = X[100*1000:, :]
    del X

    print "Saving the unlabeled data"
    data.X = unlabeled
    save_dataset(output_dir, data, 'unlabeled')
    del data
    del unlabeled

    print "Saving the labeled train data"
    supplement.X = labeled
    save_dataset(output_dir, supplement, 'train')
    del supplement
    del labeled

    print "Loading the test data"
    test = serial.load(downsampled_dir + '/test.pkl')

    print "Preprocessing the test data"
    test.apply_preprocessor(preprocessor=preprocessor, can_fit=False)

    print "Saving the test data"
    save_dataset(output_dir, test, 'test')

    serial.save(output_dir + '/preprocessor.pkl', preprocessor)
