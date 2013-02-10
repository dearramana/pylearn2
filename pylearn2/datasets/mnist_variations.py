import numpy
from pylearn2.utils import serial
from pylearn2.datasets import dense_design_matrix

class MNIST_variations(dense_design_matrix.DenseDesignMatrix):
    
    def __init__(self, which_set, variation, center = False, gcn=False,
            standardize_pixels=False, shuffle = False,
            one_hot = False, start = None, stop = None):
        """
        :param which_set: string, one of ['train','valid','test']
        :param variation: string, one of ['background_random', 'background_images',
        'rotation_background_images'.
        :param center: boolean, remove per-pixel mean across examples.
        :param gcn: boolean, enable global contrast normalization (per image, we start by
        removing mean and dividing by the per-image standard deviation).
        :param standardize_pixels: boolean, after optional GCN, standardize each pixel across
        training examples, i.e. remove its mean and divide by the per-pixel standard deviation
        measured across examples.
        :param shuffle: boolean, return the shuffled dataset.
        :param one_hot: boolean, return labels as a one-hot encoded matrix.
        :param start: integer, return only examples in range [start:end].
        :param end: integer, return only examples in range [start:end].
        """
                
        # Save the parameters as attributes
        self.which_set = which_set
        self.variation = variation
        self.center = center
        self.shuffle = shuffle
        self.one_hot = one_hot
        self.start = start
        self.stop = stop
                
        # Ensure the specified set is valid
        if which_set not in ['train', 'valid', 'test']:
            raise ValueError('Unrecognized which_set value "%s".' %
                    (which_set,)+'". Valid values are ["train","valid","test"].')
            
        # Ensure the specified mnist variation to use in valid
        if variation not in ["background_random", "background_images",
                             "rotation_background_images",]:
            raise ValueError('Unrecognized variation value "%s".' %
                    (variation,)+'". Valid values are ["background_random",' + 
                    '"background_images","rotation_background_images"].')
                    

        # Based on the value of 'variation', figure out which npy file to
        # load. pylearn2.utils.serial
        path = "${PYLEARN2_DATA_PATH}/icml07data/npy/"
        if variation == "background_random":
            filename_root = path + "mnist_background_random"
        elif variation == "background_images":
            filename_root = path + "mnist_background_images"              
        else: # variation == rotation_background_image
            filename_root = path + "mnist_rotated_background_images"
            
        # Load the dataset
        inputs, labels = self.load_from_numpy(filename_root)
 
        # (optional) Perform global contrast normalization
        # This is done across all (train,valid,test) images.
        if gcn:
            inputs = inputs - inputs.mean(axis=1)[:, None]
            inputs /= inputs.std(axis=1)[:, None]

        # (optional) Center or standardize each pixel across examples.
        # We should only use statistics from the training set for this.
        if standardize_pixels or center:
            inputs = inputs - inputs[:10000].mean(axis=0)
            if standardize_pixels:
                assert center
                inputs /= inputs[:10000].std(axis=0)
                    
        # Keep only the data related to the set specified by which_set
        # (the train set is the first 10000, the valid set if the next
        # 2000 and the test set is the last 50000)
        if which_set == "train":
            inputs = inputs[:10000]
            labels = labels[:10000]
        elif which_set == "valid":
            inputs = inputs[10000:12000]
            labels = labels[10000:12000]            
        else: # which_set == test
            inputs = inputs[12000:]
            labels = labels[12000:]

        # By default, images are transposed. Bring back to "normal" orientation.
        inputs = inputs.reshape(len(inputs), 28, 28)
        inputs = inputs.swapaxes(1,2)
        inputs = inputs.reshape(len(inputs), -1)

        # Keep only the examples between start and stop
        if start != None or stop != None:
                
            # Give start and stop their default values
            if start == None:
                start = 0
            if stop == None:
                stop == len(inputs)
                
            # Ensure start is smaller than stop
            if start >= stop:  
                raise ValueError('Invalid start and stop values "%s".' %
                (start,stop)+'". start should be smaller than stop.')
                
            # Prune the dataset according to the values of start and stop
            inputs = inputs[start:stop]
            labels = labels[start:stop]
                   
        # If required, encode the labels as onehot vectors
        if one_hot:
            one_hot = numpy.zeros((labels.shape[0],10),dtype='float32')
            for i in xrange(labels.shape[0]):
                one_hot[i,labels[i]] = 1.
            labels = one_hot
                
        # If required, shuffle the data
        if shuffle:
            inputs, labels = self.shuffle_in_unison(inputs, labels)
        
        view_converter = dense_design_matrix.DefaultViewConverter((28,28,1))
        super(MNIST_variations,self).__init__(X = inputs, y =labels,
                                              view_converter = view_converter)
            
            
    def adjust_for_viewer(self, X):
        rval = X.copy()
        
        if not self.center:
            mean_by_pixel_position = rval.mean(axis=0)
            rval -= mean_by_pixel_position
            
        rval = numpy.clip(rval, -1.0, 1.0)
            
        return rval


    def adjust_to_be_viewed_with(self, X, other, per_example = False):
        return self.adjust_for_viewer(X)
        
    def get_test_set(self):
        return MNIST_variations(which_set='test', variation=self.variation,
                                center=self.center, shuffle=self.shuffle,
                                one_hot=self.one_hot, start=self.start,
                                stop=self.stop)
    
    """
        Utility functions
    """
    def load_from_numpy(self, filename_root, mmap_mode='r'):
        # Load the data
        inputs = serial.load(filename_root+'_inputs.npy')
        labels = serial.load(filename_root+'_labels.npy')
        
        # Quick checks to ensure a proper dataset has been loaded
        assert inputs.shape == (62000, 784)
        assert labels.shape[0] == inputs.shape[0]
        
        return inputs, labels
        
    def shuffle_in_unison(self, a, b):
        assert len(a) == len(b)
        p = numpy.random.permutation(len(a))
        return a[p], b[p]
