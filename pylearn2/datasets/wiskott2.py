#! /usr/bin/env python

'''This is a loader for the dataset from Franzius, Wilbert, and
Wiskott, 2008, "Invariant object recognition with slow feature
analysis".

    @incollection{franzius2008invariant,
      title={Invariant object recognition with slow feature analysis},
      author={Franzius, Mathias and Wilbert, Niko and Wiskott, Laurenz},
      booktitle={Artificial Neural Networks-ICANN 2008},
      pages={961--970},
      year={2008},
      publisher={Springer}
    }

For more dataset information, see documentation under WiskottVideo2.__init__.
'''

import functools
import warnings
import sys
import os
import hashlib
import glob
import pdb
import numpy as np
import logging

import theano

from pylearn2.datasets import Dataset
from pylearn2.utils import string_utils, serial
from pylearn2.space import CompositeSpace, Conv2DSpace, VectorSpace

log = logging.getLogger(__name__)



def validate_config_dict(config_dict):
    '''
    When creating a WiskottVideo2 instance, certain configuration
    info is needed. This info is passed as a config_dict rather than
    as constructor arguments to WiskottVideo2 to allow one to easily
    create train/valid/test datasets with identical configuration
    using anchors in YAML files. Config dicts are validated by this
    function, and any optional parameters are initialized with default
    values.
    '''
    
    cd = config_dict

    # Check that required parameters are provided
    assert 'is_fish' in cd, 'Must specify bool is_fish in config_dict'
    
    # Fill in default values for optional parameters
    cd.setdefault('axes', ('c', 0, 1, 'b'))
    cd.setdefault('num_frames', 3)
    cd.setdefault('num_channels', 1)
    cd.setdefault('trim', 0)

    # Validate
    assert isinstance(cd['is_fish'], bool), 'is_fish must be a bool'
    assert isinstance(cd['axes'], tuple), 'axes must be a tuple'
    assert cd['num_frames'] > 0, 'num_frames must be positive'
    assert cd['num_channels'] == 1, 'only 1 channel is supported for now'
    assert cd['trim'] >= 0, 'trim must be non-negative'

    return cd



class WiskottVideo2(Dataset):
    '''Dataset from Franzius, Wilbert, and Wiskott, 2008, "Invariant
    object recognition with slow feature analysis".'''

    raw_video_size = (156,156)

    _default_seed = (17, 2, 946)

    dirs_train = ['fish_layer0_15_standard',
                  'spheres_layer0_5_standard',
                  'fish_layer2_15_standard',
                  'spheres_layer2_5_standard']

    dirs_test = ['fish_test_25_standard',
                 'spheres_test_10_standard']

    too_few_files_error = ('Too few data files found (expected: %(expected)d, '
                           'actual: %(actual)d). We looked for data in '
                           '%(root_dir)s but found either too few data files or no '
                           'data files (for example, we looked for files matching '
                           'the regex %(example)s). Is the data at that path?'
                           ' Check that your PYLEARN2_DATA_PATH environment '
                           'variable is set correctly.')

    def __init__(self, which_set, config_dict, quick = False):
        '''Create a WiskottVideo2 instance.

        Parameters
        ----------
        which_set : str
            One of 'train', 'valid', 'test'. The test set files are in
            a separate set of directories from train and valid (see
            WiskottVideo2.dirs_train and WiskottVideo2.dirs_test). The
            train and valid sets are created by loading the 1000 data
            files, shuffling them, and then taking the first 80% to be
            the training set.
        
        config_dict : dict
            Most configuration parameters are passed in via the
            config_dict. This is used instead of using constructor
            arguments to allow one to easily create train/valid/test
            datasets with identical configuration using anchors in
            YAML files. The required and optional keys in this dict are:

            'is_fish' : bool, required
                If True, the dataset produces examples of synthetic
                fish as in Fig 1 b. of Franzius et al., 2008. If
                False, it produces examples of synthetic spheres, as
                in Fig 1 a. of the same paper.

            'axes' : tuple, optional (default: ('c', 0, 1, 'b'))
                The axes ordering that should be returned by the
                dataset. Currently only ('c', 0, 1, 'b') and ('b', 0,
                1, 'c') are supported.
        
            'num_frames' : int, optional (default: 3)
                The number of consecutive frames to use when creating
                batches. For example, for num_frames = 3, when an
                iterator is created with batch_size = 30, the batch
                will contain 10 segments of 3 frames each. This really
                should be done using a Conv3DSpace, but as of the time
                this dataset is being implemented, Conv3DSpace is not
                yet in the master branch. Further, returning an
                unrolled Conv2DSpace instead, though requiring a
                little extra bookkeeping, allows more straightforward
                use of fast Conv2D routines. NOTE: when creating
                iterators, it is an error to request a batch_size not
                a multiple of num_frames.
        
            'num_channels' : int, optional (default: 1)
                Only 1 is currently supported, as the fish and sphere
                data is grayscale.
        
            'trim' : int, optional (default: 0)
                How many pixels to trim off of each edge of the
                (156,156) video frames before returning (e.g. trim = 3
                results in (150,150) frames). Useful when tweaking
                numbers of pixels in convnets.
        
        quick : bool, optional (default: False)
            The entire training dataset of 1000 files takes about one
            minute to load from a local drive (potentially much longer
            via NFS) into memory, where it occupies 5GB. For
            debugging, this one minute delay can be annoying, thus if
            quick mode is enabled, only 3 files are loaded insetad of
            1000. This mode should never be used for training, only
            for debugging.
        '''

        assert which_set in ('train', 'valid', 'test')
        self.which_set = which_set
        assert isinstance(quick, bool), 'quick must be a bool'
        self.quick = quick
        if self.quick:
            log.warn('WARNING: quick mode, loading only a few data files instead of the complete dataset.')

        # Copy config from provided dict
        config = validate_config_dict(config_dict)
        self.is_fish       = config['is_fish']
        self.axes          = config['axes']
        self.num_frames    = config['num_frames']
        self.num_channels  = config['num_channels']
        self.trim          = config['trim']

        self.video_size = tuple([dd-2*self.trim for dd in self.raw_video_size])
        for dd in self.video_size:
            assert dd > 0, 'too much trimming'

        # Load data into memory
        feature_regex = 'seq_0[0-9][0-9][0-9].zip.npy'
        label_regex   = 'seq_0[0-9][0-9][0-9].zip.labels.npy'
        # dirs_train is used for both train and valid! Separation is done in _load_data function.
        dirs = self.dirs_test if self.which_set == 'test' else self.dirs_train

        # A list of data matrices, one per short video of ~200 frames
        #   Example: self._feature_matrices[0].shape: (156, 156, 200)
        self._feature_matrices = self._load_data(dirs, feature_regex)
        # A list of label matrices, one per short video of ~200 frames
        #   Example: self._label_matrices[0].shape: (200, 29)
        self._label_matrices = self._load_data(dirs, label_regex, is_labels=True)

        if self.is_fish:
            self._target_1_matrices = [np.array(lm[:,:25]) for lm in self._label_matrices]
            self._target_2_matrices = [np.array(lm[:,25:29]) for lm in self._label_matrices]
        else:
            self._target_1_matrices = [np.array(lm[:,:10]) for lm in self._label_matrices]
            self._target_2_matrices = [np.array(lm[:,10:16]) for lm in self._label_matrices]
        
        assert len(self._feature_matrices) == len(self._label_matrices)
        self._n_matrices = len(self._feature_matrices)

        log.info('Memory used for WiskottVideo2 features/labels: %.3fG/%.3fG' % (
            sum([mat.nbytes for mat in self._feature_matrices]) / 1024. ** 3,
            sum([mat.nbytes for mat in self._label_matrices])   / 1024. ** 3
            ))

        if self.is_fish:
            #label_space = VectorSpace(dim = 29)
            label_space = CompositeSpace((
                VectorSpace(dim = 25),
                VectorSpace(dim = 4),
            ))
        else:
            # spheres
            #label_space = VectorSpace(dim = 16)
            label_space = CompositeSpace((
                VectorSpace(dim = 10),
                VectorSpace(dim = 6),
            ))

        self.space = CompositeSpace((
            Conv2DSpace(self.video_size, num_channels = 1, axes = ('b', 0, 1, 'c')),
            label_space))
        #self.source = ('features', 'targets')
        self.source = ('features', ('targets1', 'targets2'))
        self.data_specs = (self.space, self.source)


    def _load_data(self, data_directories, file_regex, is_labels=False):
        filenames = []
        root_dir = os.path.join(
            string_utils.preprocess('${PYLEARN2_DATA_PATH}'),
            'wiskott')
        for ii, data_directory in enumerate(data_directories):
            if self.is_fish and not 'fish' in data_directory:
                continue
            if not self.is_fish and not 'sphere' in data_directory:
                continue                
            file_filter = os.path.join(root_dir,
                                       data_directory, 'views',
                                       file_regex)
            example_file_filter = file_filter
            filenames.extend(sorted(glob.glob(file_filter)))
        
        expected_files = 1250 if self.which_set in ('train', 'valid') else 500
        assert len(filenames) == expected_files, (
            self.too_few_files_error % {'expected': expected_files,
                                        'actual': len(filenames),
                                        'root_dir': root_dir,
                                        'example': example_file_filter})

        # Here we split the training directories into train and valid
        # sets and choose the appropriate set. The test set is separate.
        if self.which_set in ('train', 'valid'):
            rng = np.random.RandomState(self._default_seed)
            rng.shuffle(filenames)
            idx_train = int(len(filenames) * .8)  # 80% train, 20% valid
            train_filenames = filenames[:idx_train]
            valid_filenames = filenames[idx_train:]
            assert len(train_filenames) > 0, 'too few files'
            assert len(valid_filenames) > 0, 'too few files'
            if self.which_set == 'train':
                filenames = train_filenames
            else:
                filenames = valid_filenames

        if self.quick:
            filenames = filenames[:3]
        log.info('Loading data from %d files:      ' % len(filenames))
        
        matrices = []
        n_files = len(filenames)
        for ii, filename in enumerate(filenames):
            if is_labels:
                assert ('fish' in filename) or ('spheres' in filename), 'Not sure if fish or spheres.'
                is_fish = 'fish' in filename
                mat = load_labels(filename, is_fish)   # e.g (201,16)
                matrices.append(mat)
            else:
                mat = serial.load(filename)    # e.g (156,156,201)
                # Put batch index first
                mat = np.array(np.rollaxis(mat, 2, 0), copy=True)   # e.g (201,156,156)
                # Add dimension for channels
                mat = np.reshape(mat, mat.shape + (1,))        # e.g. (201,156,156,1)
                matrices.append(mat)
            if (ii+1) % 100 == 0 or ii == (n_files-1):
                log.info('%5d' % (ii+1))
        return matrices


    @functools.wraps(Dataset.iterator)
    def iterator(self, mode=None, batch_size=None, num_batches=None,
                 topo=None, targets=None, rng=None, data_specs=None,
                 return_tuple=False, ignore_data_specs=False):

        #print 'Getting new iterator for %s dataset' % self.which_set
        #print '   rng passed is:', rng

        if self.which_set in ('valid', 'test') and rng is None:
            # valid and test sets should not be stochastic unless explicitly requested
            rng = np.random.RandomState(self._default_seed)

        # The batch_size contains the "unrolled" size, since we're returning a Conv2DSpace.
        if batch_size is None: batch_size = 10 * self.num_frames
        if num_batches is None: num_batches = 20
        assert batch_size > 0
        assert batch_size % self.num_frames == 0, (
            'Iterator must be created with batch_size = num_frames * an integer'
            )
        slices_per_batch = batch_size / self.num_frames
        assert num_batches > 0
        assert topo is None
        assert targets is None

        if mode is not None:
            warnings.warn('Ignoring iterator mode of: %s' % repr(mode))

        if not hasattr(rng, 'random_integers'):
            rng = np.random.RandomState(rng)

        return MultiplexingMatrixIterator(
            self._feature_matrices,
            self._target_1_matrices,
            self._target_2_matrices,
            incoming_axes = ('b', 0, 1, 'c'),
            data_specs = data_specs,
            num_batches = num_batches,
            num_slices = slices_per_batch,
            slice_length = self.num_frames,
            cast_to_floatX = True,
            trim = self.trim,
            video_size = self.video_size,
            rng = rng,
            descrip = '%s set' % self.which_set,
            )



class MultiplexingMatrixIterator(object):
    '''An iterator that creates samples by randomly drawing contiguous blocks
    of data from a number of lists, where the probability of drawing
    from a list is proportional to the length of the list less the slice
    length. The blocks are returned "unrolled", meaning they are stacked
    together without adding an extra dimension. Supports 'features' and
    'targets'.

    This class is somewhat hardcoded to work with the WiskottVideo2
    dataset above by requiring list_features, list_targets_1, and
    list_targets_2 arguments. TODO: decouple this.
    '''

    def __init__(self, list_features, list_targets_1, list_targets_2,
                 num_slices, slice_length, num_batches,
                 data_specs, incoming_axes, cast_to_floatX,
                 trim, video_size,
                 rng = None, descrip = ''):
        '''
        num_slices: number of slices to take. Each slice is from a different
        randomly selected matrix (with replacement).
        
        slice_length: how long each slice is within a list.
        
        For example, with num_slices = 5 and slice_length = 3, we would randomly
        choose 5 matrices and concatenate a slice of length 3 from each matrix for a
        total returned length of 15.
        '''
        
        self.list_features = list_features
        self.list_targets_1 = list_targets_1
        self.list_targets_2 = list_targets_2
        assert len(list_features) == len(list_targets_1), 'list length mismatch'
        assert len(list_features) == len(list_targets_2), 'list length mismatch'
        self.n_lists = len(list_features)
        assert num_slices > 0
        assert slice_length > 0
        for target_list in (self.list_targets_1, self.list_targets_2):
            for m1,m2 in zip(self.list_features, target_list):
                assert m1.shape[0] == m2.shape[0], 'matrix leading dimensions must match'
                assert m1.shape[0] >= slice_length, (
                    'matrix of size (%d,...) not long enough for slice of length %d' % (m1.shape[0], slice_length)
                    )
        self._num_slices = num_slices
        self._slice_length = slice_length
        assert incoming_axes in (('b', 0, 1, 'c'), ('c', 0, 1, 'b')), (
            'Unsupported incoming_axes: %s' % incoming_axes
            )        
        self.incoming_axes = incoming_axes
        
        assert num_batches > 0
        self._num_batches = num_batches
        self._returned_batches = 0
        self.cast_to_floatX = cast_to_floatX
        self.trim = trim
        self.video_size = video_size
        self.descrip = descrip
        
        # Compute max starting indices and probability for all lists
        self.max_start_idxs = [mm.shape[0] - self._slice_length for mm in self.list_features]
        probs = [mm+1 for mm in self.max_start_idxs]  # proportional to number of possible windows
        self.probabilities = np.array(probs, dtype=float)
        self.probabilities /= float(sum(self.probabilities))
        assert abs(1-sum(self.probabilities)) < 1e-10
        
        if hasattr(rng, 'random_integers'):
            self.rng = rng
        else:
            self.rng = np.random.RandomState(rng)

        # Check the data_specs
        self.data_specs = data_specs
        self.space,self.source = self.data_specs
        if not isinstance(self.source, tuple):
            self.source = (self.source,)
        if not isinstance(self.space, CompositeSpace):
            raise Exception('Not sure how to handle a non-CompositeSpace. Redo this part.')

        # Create a list of references to the appropriate data given the data_specs
        self.data_list = []
        self.block_transformer_list = []
        self.transformer_list = []
        if len(self.source) == 0:
            warnings.warn('Warning: null space? Perhaps indicative of some problem...')
        for ii,src in enumerate(self.source):
            if src not in ('features','targets1','targets2'):
                raise Exception('unknown source: %s' % src)
            spc = self.space.components[ii]
            if src == 'features':
                assert isinstance(spc, Conv2DSpace)
                assert spc.shape == self.video_size  # (156,156) or smaller after trimming
                assert spc.num_channels == 1
                self.data_list.append(self.list_features)
                self.block_transformer_list.append(lambda block: block[:,self.trim:block.shape[1]-self.trim,self.trim:block.shape[2]-self.trim])
                if self.incoming_axes == ('b',0,1,'c') and spc.axes == ('c',0,1,'b'):
                    self.transformer_list.append(lambda data : data.transpose((3,1,2,0)))
                else:
                    self.transformer_list.append(None)
            elif src == 'targets1':  # 'targets2'
                self.data_list.append(self.list_targets_1)
                self.block_transformer_list.append(None)
                self.transformer_list.append(None)
            elif src == 'targets2':  # 'targets2'
                self.data_list.append(self.list_targets_2)
                self.block_transformer_list.append(None)
                self.transformer_list.append(None)
            else:
                raise Exception('logic error')
        
    def __iter__(self):
        return self

    def next(self):
        if self._returned_batches >= self._num_batches:
            raise StopIteration
        else:
            self._returned_batches += 1

        ret_list = []
        for ii in xrange(self._num_slices):
            #list_idx = self.rng.choice(len(nFrames), 1, p = self.probabilities)[0]
            # Inefficient hack because Montreal's version of numpy is old, so we can't use the above line
            list_idx = np.argwhere(self.rng.multinomial(1, self.probabilities))[0,0]
            
            slice_start = self.rng.randint(0, self.max_start_idxs[list_idx])

            for ss,data_source in enumerate(self.data_list):
                block = data_source[list_idx][slice_start:(slice_start+self._slice_length)]

                block_transformer = self.block_transformer_list[ss]
                if block_transformer is not None:
                    block = block_transformer(block)       # e.g. to trim block

                if ii == 0:
                    # Allocate memory the first time through
                    return_shape = list(block.shape)
                    # unroll (batch,) to (batch*num_slices)
                    return_shape[0] = return_shape[0] * self._num_slices
                    dtype = theano.config.floatX if self.cast_to_floatX else block.dtype
                    ret_list.append(np.zeros(return_shape, dtype = dtype))
                
                ret_list[ss][(ii*self._slice_length):((ii+1)*self._slice_length)] = block

        # Reshape ('b',0,1,'c') -> ('c',0,1,'b') if necessary
        for ss in range(len(ret_list)):
            transformer = self.transformer_list[ss]
            if transformer is not None:
                #print 'TRANSFORMING (call %d)' % self._returned_batches
                ret_list[ss] = transformer(ret_list[ss])

        #print 'returning data %s: (%s)' % (('(%s)' % self.descrip) if self.descrip else '', ','.join([hashof(dd)[:6] for dd in ret_list]))
        #pdb.set_trace()
                
        return tuple(ret_list)

    @property
    def batch_size(self):
        ret = self._slice_length * self._num_slices
        return ret
    
    @property
    def num_batches(self):
        return self._num_batches
    
    @property
    def num_examples(self):
        return self.batch_size * self.num_batches
    
    @property
    def stochastic(self):
        return True



def load_labels(path, is_fish):
    '''
    path to a numpy file containing the labels
    is_fish: bool, True=fish, False=spheres

    numpy file has this format:
        x
        y
        one-hot encoding of label (25 elements for fish, 10 for spheres)
        sin(phi_y)         (25 elements for fish, 10 for spheres)
        cos(phi_y)        (25 elements for fish, 10 for spheres)
        sin(phi_z)         (not present for fish, they only rotate around 1
                axis, 10 elements for spheres)
        cos(phi_z)        (not present for fish, they only rotate around 1
                axis, 10 elements for spheres)

    This function loads the numpy file, collapses sin(phi_y) into one column,
    cos(phi_y) into one column, sin(phi_z) into one column, and cos(phi_z) into
    one column. It then returns data with this format:

    id (one hot)
    x
    y
    sin(phi_y)
    cos(phi_y)
    sin(phi_z)
    cos(phi_z)
    '''

    raw = np.load(path)

    if is_fish:
        assert raw.shape[1] == 77
    else:
        assert raw.shape[1] == 52

    num_feat = 16
    num_id = 10
    if is_fish:
        num_feat = 29
        num_id = 25

    batch_size = raw.shape[0]

    rval = np.zeros((batch_size, num_feat), dtype=raw.dtype)

    raw_start = 2
    ids = raw[:, raw_start:raw_start + num_id]
    raw_start += num_id
    rval[:, 0:num_id] = ids                            # IDs
    rval_start = num_id
    rval[:, rval_start:rval_start + 2] = raw[:, 0:2]   # x,y
    rval_start += 2
    for i in xrange(2 + (1 - is_fish) * 2):            # sin/cos cols
        #raw[:, rval_start] = (ids * raw[raw_start:raw_start+num_id]).sum(axis=1)
        rval[:,rval_start] = raw[:,raw_start]
        rval_start += 1
        raw_start += num_id

    assert raw_start == raw.shape[1]
    assert rval_start == rval.shape[1]

    return rval



def hashof(obj):
    '''Compute digest of object. Just for debugging.'''
    hashAlg = hashlib.sha1()
    hashAlg.update(obj)
    return hashAlg.hexdigest()



def demo():
    from fish.util import imagesc
    
    config = {}
    config['is_fish'] = True
    config['num_frames'] = 5
    
    wisk = WiskottVideo2('train', config, quick = True)

    feature_space = Conv2DSpace((156,156), num_channels = 1, axes = ('c', 0, 1, 'b'))
    if config['is_fish']:
        space = CompositeSpace((
            feature_space,
            VectorSpace(dim = 25),
            VectorSpace(dim = 4)
            ))
    else:
        space = CompositeSpace((
            feature_space,
            VectorSpace(dim = 10),
            VectorSpace(dim = 6)
            ))
    source = ('features', 'targets1', 'targets2')
    data_specs = (space, source)

    it = wisk.iterator(rng=0, data_specs = data_specs,
                       batch_size = 500)

    example = it.next()
    dat,ids,xy = example

    print 'got example with components of shape: (%s)' % (
        ', '.join([repr(ee.shape) for ee in example])
        )

    for ii,ee in enumerate(example):
        print '  Mean of example[%d] is:' % ii, ee.mean()
        
    print 'done, dropping into debugger (q to quit).'
    pdb.set_trace()



if __name__ == '__main__':
    demo()