"""

Classes that define how vector spaces are formatted

Most of our models can be viewed as linearly transforming
one vector space to another. These classes define how the
vector spaces should be represented as theano/numpy
variables.

For example, the VectorSpace class just represents a
vector space with a vector, and the model can transform
between spaces with a matrix multiply. The Conv2DSpace
represents a vector space as an image, and the model
can transform between spaces with a 2D convolution.

To make models as general as possible, models should be
written in terms of Spaces, rather than in terms of
numbers of hidden units, etc. The model should also be
written to transform between spaces using a generic
linear transformer from the pylearn2.linear module.

The Space class is needed so that the model can specify
what kinds of inputs it needs and what kinds of outputs
it will produce when communicating with other parts of
the library. The model also uses Space objects internally
to allocate parameters like hidden unit bias terms in
the right space.

"""
__authors__ = "Ian Goodfellow"
__copyright__ = "Copyright 2010-2012, Universite de Montreal"
__credits__ = ["Ian Goodfellow"]
__license__ = "3-clause BSD"
__maintainer__ = "Ian Goodfellow"
__email__ = "goodfeli@iro"

import warnings
import numpy as np
import theano.tensor as T
import theano.sparse
from theano.tensor import TensorType
from theano import config
import functools
from theano.gof.op import get_debug_values
from theano.sandbox.cuda.type import CudaNdarrayType
from pylearn2.utils import py_integer_types, safe_zip
#import pylearn2.utils.data_specs as specs_utils


class Space(object):
    """A vector space that can be transformed by a linear operator."""

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return str(self)

    def get_origin(self):
        """
        Returns the origin in this space.

        Returns
        -------
        origin : ndarray
            An NumPy array, the shape of a single points in this
            space, representing the origin.
        """
        raise NotImplementedError()

    def get_origin_batch(self, n):
        """
        Returns a batch containing `n` copies of the origin.

        Returns
        -------
        batch : ndarray
            A NumPy array in the shape of a batch of `n` points in this
            space (with points being indexed along the first axis),
            each `batch[i]` being a copy of the origin.
        """
        raise NotImplementedError()

    def make_theano_batch(self, name=None, dtype=None):
        """
        Returns a symbolic variable representing a batch of points
        in this space.

        Returns
        -------
        batch : TensorVariable
            A batch with the appropriate number of dimensions and
            appropriate broadcast flags to represent a batch of
            points in this space.
        """
        raise NotImplementedError()

    def make_batch_theano(self, name = None, dtype = None):
        """ An alias to make_theano_batch """

        return self.make_theano_batch(name = name, dtype = dtype)

    def get_total_dimension(self):
        """
        Returns a Python int (not a theano iscalar) representing
        the dimensionality of a point in this space.

        If you format a batch of examples in this space as a
        design matrix (i.e., VectorSpace batch) then the
        number of columns will be equal to the total dimension.
        """

        raise NotImplementedError(str(type(self))+" does not implement get_total_dimension.")

    def np_format_as(self, batch, space):
        """
        batch: numpy ndarray which lies in the space represented by self
        space: a Space

        returns batch formatted to lie in space

        Should be invertible, i.e.
        batch should equal
        space.format_as(self.format_as(batch, space), self)
        """
        if not hasattr('_np_format_as', self):
            #assert specs_utils.is_flat_space(self)
            variables = self.make_theano_batch()
            outputs = self.format_as(variables, space)
            if not isinstance(variables, (tuple, list)):
                variables = (variables,)
            self._np_format_as = theano.function(variables, outputs)
        if isinstance(batch, (list, tuple)):
            return self._np_format_as(*batch)
        else:
            return self._np_format_as(batch)



    def format_as(self, batch, space):
        """
        batch: a theano batch which lies in the space represented by self
        space: a Space

        returns batch formatted to lie in space

        Should be invertible, i.e.
        batch should equal
        space.format_as(self.format_as(batch, space), self)
        """

        self.validate(batch)

        my_dimension =  self.get_total_dimension()
        other_dimension = space.get_total_dimension()

        if my_dimension != other_dimension:
            raise ValueError(str(self)+" with total dimension " +
                    str(my_dimension) + " can't format a batch into " +
                    str(space) + "because its total dimension is " +
                    str(other_dimension))

        if self == space:
            rval = batch
        else:
            rval = self._format_as(batch, space)

        return rval

    def _format_as(self, batch, space):
        """
        Helper method that implements specifics of format_as for a particular subclass.
        """

        raise NotImplementedError(str(type(self))+" does not implement _format_as.")

    def validate(self, batch):
        """ Raises an exception if batch is not a valid theano batch
        in this space. """

        raise NotImplementedError(str(type(self))+" does not implement validate.")

    def batch_size(self, batch):
        """
        Read the batch size out of a batch.
        """
        warnings.warn("Space.batch_size(batch) is deprecated, please use "
                "Space.get_batch_size(batch) instead.",
                stacklevel=2)
        return self.get_batch_size(batch)

    def get_batch_size(self, data):
        """ Returns the batch size of the given data """

        raise NotImplementedError(str(type(self))+" does not implement "+\
                                  "get_batch_size")

    def get_batch(self, data, start, end):
        """ Returns a batch of data starting from index `start` to index
        `stop`"""
        raise NotImplementedError(str(type(self))+" does not implement "+\
                                  "get_batch")


class VectorSpace(Space):
    """A space whose points are defined as fixed-length vectors."""
    def __init__(self, dim, sparse=False):
        """
        Initialize a VectorSpace.

        Parameters
        ----------
        dim : int
            Dimensionality of a vector in this space.
        sparse: bool
            Sparse vector or not
        """
        self.dim = dim
        self.sparse = sparse

    def __str__(self):
        return '%(classname)s(dim=%(dim)s%(sparse)s)' % dict(
                classname=self.__class__.__name__,
                dim=self.dim,
                sparse=(', sparse' if self.sparse else ''))

    @functools.wraps(Space.get_origin)
    def get_origin(self):
        return np.zeros((self.dim,))

    @functools.wraps(Space.get_origin_batch)
    def get_origin_batch(self, n):
        return np.zeros((n, self.dim))

    @functools.wraps(Space.get_batch_size)
    def get_batch_size(self, data):
        self.validate(data)
        return data.shape[0]

    @functools.wraps(Space.make_theano_batch)
    def make_theano_batch(self, name=None, dtype=None):
        if dtype is None:
            dtype = config.floatX

        if self.sparse:
            rval = theano.sparse.csr_matrix(name=name)
        else:
            rval = T.matrix(name=name, dtype=dtype)
        if config.compute_test_value != 'off':
            rval.tag.test_value = self.get_origin_batch(n=4)
        return rval

    @functools.wraps(Space.get_total_dimension)
    def get_total_dimension(self):
        return self.dim

    @functools.wraps(Space.np_format_as)
    def np_format_as(self, batch, space):
        return self._format_as(batch, space)

    @functools.wraps(Space._format_as)
    def _format_as(self, batch, space):

        if isinstance(space, CompositeSpace):
            pos = 0
            pieces = []
            for component in space.components:
                width = component.get_total_dimension()
                subtensor = batch[:,pos:pos+width]
                pos += width
                formatted = VectorSpace(width).format_as(subtensor, component)
                pieces.append(formatted)
            return tuple(pieces)

        if isinstance(space, Conv2DSpace):
            dims = { 'b' : batch.shape[0], 'c' : space.num_channels, 0 : space.shape[0], 1 : space.shape[1] }
            if space.axes[0] != 'b':
                tmp_axes = ['b'] + [axis for axis in space.axes if axis != 'b']
                shape = [dims[ax] for ax in tmp_axes]
                batch = batch.reshape(shape)
                batch = batch.dimshuffle(*[tmp_axes.index(ax) for ax in space.axes])
                return batch

            shape = tuple( [ dims[elem] for elem in space.axes ] )

            rval = batch.reshape(shape)

            return rval

        raise NotImplementedError(str(self)+" doesn't know how to format as "+str(space))

    def __eq__(self, other):
        return type(self) == type(other) and self.dim == other.dim

    def __hash__(self):
        return hash((type(self), self.dim))

    def validate(self, batch):
        if not isinstance(batch, theano.gof.Variable):
            raise TypeError("VectorSpace batch should be a theano Variable, got "+str(type(batch)))
        if not self.sparse and not isinstance(batch.type, (theano.tensor.TensorType, CudaNdarrayType)):
            raise TypeError("VectorSpace batch should be TensorType or CudaNdarrayType, got "+str(batch.type))
        if self.sparse and not isinstance(batch.type, theano.sparse.SparseType):
            raise TypeError()
        if batch.ndim != 2:
            raise ValueError('VectorSpace batches must be 2D, got %d dimensions' % batch.ndim)


class Conv2DSpace(Space):
    """A space whose points are defined as (multi-channel) images."""
    def __init__(self, shape, channels = None, num_channels = None, axes = None):
        """
        Initialize a Conv2DSpace.

        Parameters
        ----------
        shape : sequence, length 2
            The shape of a single image, i.e. (rows, cols).
        num_channels: int     (synonym: channels)
            Number of channels in the image, i.e. 3 if RGB.
        axes: A tuple indicating the semantics of each axis.
                'b' : this axis is the batch index of a minibatch.
                'c' : this axis the channel index of a minibatch.
                <i>  : this is topological axis i (i.e., 0 for rows,
                                  1 for cols)

                For example, a PIL image has axes (0, 1, 'c') or (0, 1).
                The pylearn2 image displaying functionality uses
                    ('b', 0, 1, 'c') for batches and (0, 1, 'c') for images.
                theano's conv2d operator uses ('b', 'c', 0, 1) images.
        """

        assert (channels is None) + (num_channels is None) == 1
        if num_channels is None:
            num_channels = channels

        assert isinstance(num_channels, py_integer_types)

        if not hasattr(shape, '__len__') or len(shape) != 2:
            raise ValueError("shape argument to Conv2DSpace must be length 2")
        assert all(isinstance(elem, py_integer_types) for elem in shape)
        assert all(elem > 0 for elem in shape)
        assert isinstance(num_channels, py_integer_types)
        assert num_channels > 0
        self.shape = shape
        self.num_channels = num_channels
        if axes is None:
            # Assume pylearn2's get_topological_view format, since this is how
            # data is currently served up. If we make better iterators change
            # default to ('b', 'c', 0, 1) for theano conv2d
            axes = ('b', 0, 1, 'c')
        assert len(axes) == 4
        self.axes = axes

    def __str__(self):
        return "Conv2DSpace{shape=%s,num_channels=%d}" % (str(self.shape), self.num_channels)

    def __eq__(self, other):
        return type(self) == type(other) and \
                self.shape == other.shape and \
                self.num_channels == other.num_channels \
                and tuple(self.axes) == tuple(other.axes)

    def __hash__(self):
        return hash((type(self), self.shape, self.num_channels, self.axes))

    @functools.wraps(Space.get_origin)
    def get_origin(self):
        dims = { 0: self.shape[0], 1: self.shape[1], 'c' : self.num_channels }
        shape = [ dims[elem] for elem in self.axes if elem != 'b' ]
        return np.zeros(shape)

    @functools.wraps(Space.get_origin_batch)
    def get_origin_batch(self, n):
        if not isinstance(n, py_integer_types):
            raise TypeError("Conv2DSpace.get_origin_batch expects an int, got " +
                    str(n) + " of type " + str(type(n)))
        assert n > 0
        dims = { 'b' : n, 0: self.shape[0], 1: self.shape[1], 'c' : self.num_channels }
        shape = [ dims[elem] for elem in self.axes ]
        return np.zeros(shape)

    @functools.wraps(Space.make_theano_batch)
    def make_theano_batch(self, name=None, dtype=None):
        if dtype is None:
            dtype = config.floatX

        broadcastable = [False] * 4
        broadcastable[self.axes.index('c')] = (self.num_channels == 1)
        broadcastable = tuple(broadcastable)

        rval = TensorType(dtype=dtype,
                          broadcastable=broadcastable
                         )(name=name)
        if config.compute_test_value != 'off':
            rval.tag.test_value = self.get_origin_batch(n=4)
        return rval

    @functools.wraps(Space.get_batch_size)
    def get_batch_size(self, data):
        self.validate(data)
        return data.shape[self.axes.index('b')]


    @staticmethod
    def convert(tensor, src_axes, dst_axes):
        """
            tensor: a 4 tensor representing a batch of images

            src_axes: the axis semantics of tensor

            Returns a view of tensor using the axis semantics defined
            by dst_axes. (If src_axes matches dst_axes, returns
            tensor itself)

            Useful for transferring tensors between different
            Conv2DSpaces.
        """
        src_axes = tuple(src_axes)
        dst_axes = tuple(dst_axes)
        assert len(src_axes) == 4
        assert len(dst_axes) == 4

        if src_axes == dst_axes:
            return tensor

        shuffle = [ src_axes.index(elem) for elem in dst_axes ]

        return tensor.dimshuffle(*shuffle)

    @staticmethod
    def convert_numpy(tensor, src_axes, dst_axes):
        """
            tensor: a 4 tensor representing a batch of images

            src_axes: the axis semantics of tensor

            Returns a view of tensor using the axis semantics defined
            by dst_axes. (If src_axes matches dst_axes, returns
            tensor itself)

            Useful for transferring tensors between different
            Conv2DSpaces.
        """
        src_axes = tuple(src_axes)
        dst_axes = tuple(dst_axes)
        assert len(src_axes) == 4
        assert len(dst_axes) == 4

        if src_axes == dst_axes:
            return tensor

        shuffle = [ src_axes.index(elem) for elem in dst_axes ]

        return tensor.transpose(*shuffle)

    @functools.wraps(Space.get_total_dimension)
    def get_total_dimension(self):

        # Patch old pickle files
        if not hasattr(self, 'num_channels'):
            self.num_channels = self.nchannels

        return self.shape[0] * self.shape[1] * self.num_channels

    @functools.wraps(Space.validate)
    def validate(self, batch):
        if not isinstance(batch, theano.gof.Variable):
            raise TypeError("Conv2DSpace batches must be theano Variables, got "+str(type(batch)))
        if not isinstance(batch.type, (theano.tensor.TensorType,CudaNdarrayType)):
            raise TypeError()
        if batch.ndim != 4:
            raise ValueError()
        for val in get_debug_values(batch):
            d = self.axes.index('c')
            actual_channels = val.shape[d]
            if actual_channels != self.num_channels:
                raise ValueError("Expected axis "+str(d)+" to be number of channels ("+str(self.num_channels)+\
                        ") but it is "+str(actual_channels))
            assert val.shape[self.axes.index('c')] == self.num_channels
            for coord in [0,1]:
                d = self.axes.index(coord)
                actual_shape = val.shape[d]
                expected_shape = self.shape[coord]
                if actual_shape != expected_shape:
                    raise ValueError("Conv2DSpace with shape "+str(self.shape) + \
                            " and axes " + str(self.axes) + " expected dimension " + \
                            str(d) + " of a batch (" + str(batch)+") to have length " + str(expected_shape) + \
                            " but it has "+str(actual_shape))

    @functools.wraps(Space.np_format_as)
    def np_format_as(self, batch, space):
        if isinstance(space, VectorSpace):
            if self.axes[0] != 'b':
                # We need to ensure that the batch index goes on the first axis before the reshape
                new_axes = ['b'] + [axis for axis in self.axes if axis != 'b']
                batch = batch.transpose(*[self.axes.index(axis) for axis in new_axes])
            return batch.reshape((batch.shape[0], self.get_total_dimension()))
        if isinstance(space, Conv2DSpace):
            return Conv2DSpace.convert_numpy(batch, self.axes, space.axes)
        raise NotImplementedError("Conv2DSPace doesn't know how to format as "+str(type(space)))


    @functools.wraps(Space._format_as)
    def _format_as(self, batch, space):
        self.validate(batch)
        if isinstance(space, VectorSpace):
            if self.axes[0] != 'b':
                # We need to ensure that the batch index goes on the first axis before the reshape
                new_axes = ['b'] + [axis for axis in self.axes if axis != 'b']
                batch = batch.dimshuffle(*[self.axes.index(axis) for axis in new_axes])
            return batch.reshape((batch.shape[0], self.get_total_dimension()))
        if isinstance(space, Conv2DSpace):
            return Conv2DSpace.convert(batch, self.axes, space.axes)
        raise NotImplementedError("Conv2DSPace doesn't know how to format as "+str(type(space)))


class CompositeSpace(Space):
    """A Space whose points are tuples of points in other spaces """
    def __init__(self, components):
        assert isinstance(components, (list, tuple))
        self.num_components = len(components)
        assert all([isinstance(component, Space) for component in components])
        self.components = list(components)

    def __eq__(self, other):
        return type(self) == type(other) and \
            len(self.components) == len(other.components) and \
            all([my_component == other_component for
                my_component, other_component in \
                zip(self.components, other.components)])

    def __hash__(self):
        return hash((type(self), tuple(self.components)))

    def __str__(self):
        return '%(classname)s(%(components)s)' % dict(
                classname=self.__class__.__name__,
                components=', '.join([str(c) for c in self.components]))

    def restrict(self, subset):
        """Returns a new Space containing only the components whose indices
        are given in subset.

        The new space will contain the components in the order given in the
        subset list.

        Note that the returned Space may not be a CompositeSpace if subset
        contains only one index.
        """

        assert isinstance(subset, (list, tuple))

        if len(subset) == 1:
            idx, = subset
            return self.components[idx]

        return CompositeSpace([self.components[i] for i in subset])

    def restrict_batch(self, batch, subset):
        """Returns a batch containing only the components whose indices are present
        in subset. May not be a tuple anymore if there is only one index. Outputs
        will be ordered in the order that they appear in subset."""

        self.validate(batch)
        assert isinstance(subset, (list, tuple))

        if len(subset) == 1:
            idx, = subset
            return batch[idx]

        return tuple([batch[i] for i in subset])

    @functools.wraps(Space.get_total_dimension)
    def get_total_dimension(self):
        return sum([component.get_total_dimension() for component in
            self.components])

    @functools.wraps(Space.np_format_as)
    def np_format_as(self, batch, space):
        if isinstance(space, VectorSpace):
            pieces = []
            for component, input_piece in zip(self.components, batch):
                width = component.get_total_dimension()
                pieces.append(component.np_format_as(input_piece, VectorSpace(width)))
            return np.concatenate(pieces, axis=1)

        raise NotImplementedError(str(self)+" does not know how to format as "+str(space))

    @functools.wraps(Space._format_as)
    def _format_as(self, batch, space):
        if isinstance(space, VectorSpace):
            pieces = []
            for component, input_piece in zip(self.components, batch):
                width = component.get_total_dimension()
                pieces.append(component.format_as(input_piece, VectorSpace(width)))
            return T.concatenate(pieces, axis=1)

        raise NotImplementedError(str(self)+" does not know how to format as "+str(space))

    @functools.wraps(Space.validate)
    def validate(self, batch):
        if not isinstance(batch, tuple):
            raise TypeError()
        if len(batch) != self.num_components:
            raise ValueError("Expected "+str(self.num_components)+" elements in batch, "
                    "got " + str(len(batch)))
        for batch_elem, component in zip(batch, self.components):
            component.validate(batch_elem)

    @functools.wraps(Space.get_origin_batch)
    def get_origin_batch(self, n):
        return tuple([component.get_origin_batch(n) for component in self.components])

    @functools.wraps(Space.make_theano_batch)
    def make_theano_batch(self, name=None, dtype=None):
        if name is None:
            name = [None] * len(self.components)
        elif not isinstance(name, (list, tuple)):
            name = ['%s[%i]' % (name, i) for i in xrange(len(self.components))]

        if dtype is None:
            dtype = [None] * len(self.components)
        assert isinstance(name, (list, tuple))
        assert isinstance(dtype, (list, tuple))

        rval = tuple([x.make_theano_batch(name=n, dtype=d)
                for x,n,d in safe_zip(self.components,
                                      name,
                                      dtype)])
        return rval

    @functools.wraps(Space.get_batch_size)
    def get_batch_size(self, data):
        # All components should have the same effective batch size,
        # with the exeption of NullSpace, and CompositeSpace with
        # 0 components, which will return 0, because they do not
        # represent any data.
        self.validate(data)

        for c, d in safe_zip(self.components, data):
            b = c.get_batch_size(d)

            if b != 0:
                # We assume they are all equal to b
                return b

        # All components are empty
        return 0


class NullSpace(Space):
    """
    A space that contains no data.

    When symbolic or numerical data for that space actually has to be
    represented, None is used as a placeholder.

    The source associated to that Space is the empty string ('').
    """

    def __str__(self):
        return "NullSpace"

    def __eq__(self, other):
        return type(self) == type(other)

    def __hash__(self):
        return hash(type(self))

    @functools.wraps(Space.make_theano_batch)
    def make_theano_batch(self, name=None, dtype=None):
        return None

    @functools.wraps(Space.validate)
    def validate(self, batch):
        if batch is not None:
            raise TypeError("NullSpace only accepts 'None' as a "
                    "place-holder for data, not %s of type %s"
                    % (batch, type(batch)))

    @functools.wraps(Space.np_format_as)
    def np_format_as(self, batch, space):
        assert isinstance(space, NullSpace)
        assert batch is None
        return None

    @functools.wraps(Space._format_as)
    def _format_as(self, batch, space):
        self.validate(batch)
        assert isinstance(space, NullSpace)
        return None

    @functools.wraps(Space.get_batch_size)
    def get_batch_size(self, data):
        # There is no way to know how many examples would actually
        # have been in the batch, since it is empty. We return 0.
        self.validate(data)
        return 0
