"""
Makes a version of the STL-10 dataset that has been downsampled
by a factor of 3 along both axes.

This is to mimic the first step of preprocessing used in
'An Analysis of Single-Layer Networks in Unsupervised Feature Learning'
by Adam Coates, Honglak Lee, and Andrew Y. Ng

This script also translates the data to lie in [-127.5, 127.5]
instead of [0,255].
This makes it play nicer with some of pylearn's visualization tools.
"""

from pylearn2.datasets.stl10 import STL10
from pylearn2.datasets.preprocessing import Downsample
from pylearn2.utils import string_utils as string
from pylearn2.utils import serial
import numpy as np


def create_output_dir(data_dir):
    """
    Preparation of the directory.

    Parameters
    ----------
    data_dir: str
        Path of the stl10 directory.
    """
    downsampled_dir = data_dir + '/stl10_32x32'
    serial.mkdir(downsampled_dir)
    README = open(downsampled_dir + '/README', 'w')

    README.write("""
    The .pkl files in this directory may be opened in python using
    cPickle, pickle, or pylearn2.serial.load. They contain pylearn2
    Dataset objects defining the STL-10 dataset, but downsampled to
    size 32x32 and translated to lie in [-127.5, 127.5 ].

    They were created with the pylearn2 script make_downsampled_stl10.py

    All other files in this directory, including this README, were
    created by the same script and are necessary for the other files
    to function correctly.
    """)

    README.close()

    return downsampled_dir


def save_dataset(downsampled_dir, dataset, name):
    """
    Save the newly created dataset to the given directory.

    Parameters
    ----------
    downsampled_dir: str
        Path of the directory where to save the dataset.
    dataset: pylearn2.datasets.Dataset
        The dataset to save.
    name: str
        Name of the file to save.
    """
    dataset.enable_compression()
    dataset.use_design_loc(downsampled_dir + '/' + name + '.npy')
    serial.save(downsampled_dir + '/' + name + '.pkl', dataset)

if __name__ == "__main__":
    data_dir = string.preprocess('${PYLEARN2_DATA_PATH}')

    print 'Preparing output directory...'
    downsampled_dir = create_output_dir(data_dir)

    preprocessor = Downsample(sampling_factor=[3, 3])

    # Unlabeled dataset is huge, so do it in chunks
    # (After downsampling it should be small enough to work with)
    final_unlabeled = np.zeros((100*1000, 32*32*3), dtype='float32')

    for i in xrange(10):
        print 'Loading unlabeled chunk '+str(i+1)+'/10...'
        unlabeled = STL10(which_set='unlabeled', center=True,
                          example_range=(i * 10000, (i+1) * 10000))

        print 'Preprocessing unlabeled chunk...'
        print 'before ', (unlabeled.X.min(), unlabeled.X.max())
        unlabeled.apply_preprocessor(preprocessor)
        print 'after ', (unlabeled.X.min(), unlabeled.X.max())

        final_unlabeled[i*10000:(i+1)*10000, :] = unlabeled.X

    unlabeled.set_design_matrix(final_unlabeled)

    print 'Saving unlabeleding set...'
    save_dataset(downsampled_dir, unlabeled, 'unlabeled')

    del unlabeled
    import gc
    gc.collect()

    print 'Loading testing set...'
    test = STL10(which_set='test', center=True)

    print 'Preprocessing testing set...'
    print 'before ', (test.X.min(), test.X.max())
    test.apply_preprocessor(preprocessor)
    print 'after ', (test.X.min(), test.X.max())

    print 'Saving testing set...'
    save_dataset(downsampled_dir, test, 'test')
    del test

    print 'Loading training set...'
    train = STL10(which_set='train', center=True)

    print 'Preprocessing training set...'
    print 'before ', (train.X.min(), train.X.max())
    train.apply_preprocessor(preprocessor)
    print 'after ', (train.X.min(), train.X.max())

    print 'Saving training set...'
    save_dataset(downsampled_dir, train, 'train')

    del train
