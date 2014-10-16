import os
import cPickle
import numpy as np

from pylearn2.datasets.dense_design_matrix import DenseDesignMatrix
from pylearn2.datasets.augment_input import augment_input
from pylearn2.utils import serial

'''
    Loads MNIST dataset and build augmented dataset
    for DBM discriminative finetuning
'''

class MNISTAUGMENTED(DenseDesignMatrix):
    
    def __init__(self, dataset, which_set, model, mf_steps, one_hot = True,
                 start = None, stop = None):
        
        path = os.path.join('${PYLEARN2_DATA_PATH}', 'mnist')
        path = serial.preprocess(path)
        
        try:
            if which_set == 'train':
                datasets = load_from_dump(dump_data_dir = path, dump_filename = 'aug_train_dump.pkl.gz')
                augmented_X, y = datasets[0], datasets[1]
            else:
                datasets = load_from_dump(dump_data_dir = path, dump_filename = 'aug_test_dump.pkl.gz')
                augmented_X, y = datasets[0], datasets[1]
        except:
            X = dataset.X
            if one_hot:
                one_hot = np.zeros((dataset.y.shape[0], 10), dtype='float32')
                for i in xrange(dataset.y.shape[0]):
                    label = dataset.y[i]
                    one_hot[i, label] = 1.
                y = one_hot
            else:
                y = dataset.y
        
            # BUILD AUGMENTED INPUT FOR FINETUNING
            augmented_X = augment_input(X, model, mf_steps)
            
            datasets = augmented_X, y
            if which_set == 'train':
                save_to_dump(var_to_dump = datasets, dump_data_dir = path, dump_filename = 'aug_train_dump.pkl.gz')
            else:
                save_to_dump(var_to_dump = datasets, dump_data_dir = path, dump_filename = 'aug_test_dump.pkl.gz')
        
        augmented_X, y = augmented_X[start:stop], y[start:stop]
        super(MNISTAUGMENTED, self).__init__(X = augmented_X, y = y)

def load_from_dump(dump_data_dir, dump_filename):
    load_file = open(dump_data_dir + "/" + dump_filename)
    unpickled_var = cPickle.load(load_file)
    load_file.close()
    return unpickled_var

def save_to_dump(var_to_dump, dump_data_dir, dump_filename):
    save_file = open(dump_data_dir + "/" + dump_filename, 'wb')  # this will overwrite current contents
    cPickle.dump(var_to_dump, save_file, -1)  # the -1 is for HIGHEST_PROTOCOL
    save_file.close()
