import os

from .general import is_iterable
import theano
# Delay import of pylearn2.config.yaml_parse and pylearn2.datasets.control
# to avoid circular imports
yaml_parse = None
control = None
from itertools import izip
cuda = None

import numpy
np = numpy

from functools import partial
WRAPPER_ASSIGNMENTS = ('__module__', '__name__')
WRAPPER_CONCATENATIONS = ('__doc__',)
WRAPPER_UPDATES = ('__dict__',)

def make_name(variable, anon="anonymous_variable"):
    """
    If variable has a name, returns that name. Otherwise, returns anon.

    Parameters
    ----------
    variable : tensor_like
        WRITEME

    Returns
    -------
    WRITEME
    """

    if hasattr(variable,'name') and variable.name is not None:
        return variable.name

    return anon


def sharedX(value, name=None, borrow=False):
    """
    Transform value into a shared variable of type floatX

    Parameters
    ----------
    value : WRITEME
    name : WRITEME
    borrow : WRITEME

    Returns
    -------
    WRITEME
    """
    return theano.shared(theano._asarray(value, dtype=theano.config.floatX),
         name=name,
         borrow=borrow)


def as_floatX(variable):
    """
    Casts a given variable into dtype `config.floatX`. Numpy ndarrays will
    remain numpy ndarrays, python floats will become 0-D ndarrays and
    all other types will be treated as theano tensors

    Parameters
    ----------
    variable : WRITEME

    Returns
    -------
    WRITEME
    """

    if isinstance(variable, float):
        return numpy.cast[theano.config.floatX](variable)

    if isinstance(variable, numpy.ndarray):
        return numpy.cast[theano.config.floatX](variable)

    return theano.tensor.cast(variable, theano.config.floatX)


def constantX(value):
    """
    Returns a constant of value `value` with floatX dtype

    Parameters
    ----------
    variable : WRITEME

    Returns
    -------
    WRITEME
    """
    return theano.tensor.constant(numpy.asarray(value,
                                                dtype=theano.config.floatX))


def subdict(d, keys):
    """
    Create a subdictionary of d with the keys in keys

    Parameters
    ----------
    d : WRITEME
    keys : WRITEME

    Returns
    -------
    WRITEME
    """
    result = {}
    for key in keys:
        if key in d: result[key] = d[key]
    return result

def get_dimshuffle_pattern(axes, ndim):
    """
    For given axes and number of dimensions arguments of a parameter matrix or tensor
    that we want to apply a norm constraint on. This function creates a dimshuffle pattern
    in order to perform the dimshuffling over the scale variable to do elemwise product
    with the parameter matrix/matrix that we want to apply the constraint on.

    Parameters
    ----------
    axes : tuple
    WRITEME
    ndim : int
    WRITEME

    Returns
    -------
    dimshuffle_pattern : tuple
    """

    assert axes is not None, "axes should not be empty."
    assert type(axes) == tuple, "the type of axes should be a tuple."

    shf_dim_count = 0
    dimshuffle_pattern = []

    for i in xrange(ndim):
        if i in axes:
            dimshuffle_pattern.append('x')
        else:
            dimshuffle_pattern.append(shf_dim_count)
            shf_dim_count += 1

    return dimshuffle_pattern

def safe_update(dict_to, dict_from):
    """
    Like dict_to.update(dict_from), except don't overwrite any keys.

    Parameters
    ----------
    dict_to : WRITEME
    dict_from : WRITEME

    Returns
    -------
    WRITEME
    """
    for key, val in dict(dict_from).iteritems():
        if key in dict_to:
            raise KeyError(key)
        dict_to[key] = val
    return dict_to


class CallbackOp(theano.gof.Op):
    """
    A Theano Op that implements the identity transform but also does an
    arbitrary (user-specified) side effect.
    """
    view_map = { 0: [0] }

    def __init__(self, callback):
        """
        .. todo::

            WRITEME
        """
        self.callback = callback

    def make_node(self, xin):
        """
        .. todo::

            WRITEME
        """
        xout = xin.type.make_variable()
        return theano.gof.Apply(op=self, inputs=[xin], outputs=[xout])

    def perform(self, node, inputs, output_storage):
        """
        .. todo::

            WRITEME
        """
        xin, = inputs
        xout, = output_storage
        xout[0] = xin
        self.callback(xin)

    def grad(self, inputs, output_gradients):
        """
        .. todo::

            WRITEME
        """
        return output_gradients

    def R_op(self, inputs, eval_points):
        """
        .. todo::

            WRITEME
        """
        return [x for x in eval_points]

    def __eq__(self, other):
        """
        .. todo::

            WRITEME
        """
        return type(self) == type(other) and self.callback == other.callback

    def hash(self):
        """
        .. todo::

            WRITEME
        """
        return hash(self.callback)


def get_dataless_dataset(model):
    """
    Loads the dataset that model was trained on, without loading data.
    This is useful if you just need the dataset's metadata, like for
    formatting views of the model's weights.

    Parameters
    ----------
    model : WRITEME

    Returns
    -------
    WRITEME
    """

    global yaml_parse
    global control

    if yaml_parse is None:
        from pylearn2.config import yaml_parse

    if control is None:
        from pylearn2.datasets import control

    control.push_load_data(False)
    try:
        rval = yaml_parse.load(model.dataset_yaml_src)
    finally:
        control.pop_load_data()
    return rval

def safe_zip(*args):
    """
    Like zip, but ensures arguments are of same length
    """
    base = len(args[0])
    for i, arg in enumerate(args[1:]):
        if len(arg) != base:
            raise ValueError("Argument 0 has length "+str(base)+\
                " but argument "+str(i+1)+" has length "+str(len(arg)))
    return zip(*args)

# TODO: Is this a duplicate?
def safe_izip(*args):
    """
    Like izip, but ensures arguments are of same length
    """
    assert all([len(arg) == len(args[0]) for arg in args])
    return izip(*args)

def gpu_mem_free():
    """
    .. todo::

        WRITEME
    """
    global cuda
    if cuda is None:
        from theano.sandbox import cuda
    return cuda.mem_info()[0]/1024./1024

class _ElemwiseNoGradient(theano.tensor.Elemwise):
    """
    .. todo::

        WRITEME
    """
    def connection_pattern(self, node):
        """
        .. todo::

            WRITEME
        """
        return [ [ False ] ]

    def grad(self, inputs, output_gradients):
        """
        .. todo::

            WRITEME
        """
        return [ theano.gradient.DisconnectedType()() ]

# Call this on a theano variable to make a copy of that variable
# No gradient passes through the copying operation
# This is equivalent to making my_copy = var.copy() and passing
# my_copy in as part of consider_constant to tensor.grad
# However, this version doesn't require as much long range
# communication between parts of the code
block_gradient = _ElemwiseNoGradient(theano.scalar.identity)


def safe_union(a, b):
    """
    Does the logic of a union operation without the non-deterministic ordering
    of python sets.

    Parameters
    ----------
    a : WRITEME
    b : WRITEME

    Returns
    -------
    WRITEME
    """
    if not isinstance(a, list):
        raise TypeError("Expected first argument to be a list, but got " +
                        str(type(a)))
    assert isinstance(b, list)
    c = []
    for x in a + b:
        if x not in c:
            c.append(x)
    return c

# This was moved to theano, but I include a link to avoid breaking
# old imports
from theano.printing import hex_digest

def function(*args, **kwargs):
    """
    A wrapper around theano.function that disables the on_unused_input error.
    Almost no part of pylearn2 can assume that an unused input is an error, so
    the default from theano is inappropriate for this project.
    """
    return theano.function(*args, on_unused_input='ignore', **kwargs)

def grad(*args, **kwargs):
    """
    A wrapper around theano.gradient.grad that disable the disconnected_inputs
    error. Almost no part of pylearn2 can assume that a disconnected input
    is an error.
    """
    return theano.gradient.grad(*args, disconnected_inputs='ignore', **kwargs)

# Groups of Python types that are often used together in `isinstance`
py_integer_types = (int, long, np.integer)
py_float_types = (float, np.floating)
py_complex_types = (complex, np.complex)
py_number_types = (int, long, float, complex, np.number)


def get_choice(choice_to_explanation):
    """
    WRITEME

    Parameters
    ----------
    choice_to_explanation : dict
        Dictionary mapping possible user responses to strings describing what \
        that response will cause the script to do

    Returns
    -------
    WRITEME
    """
    d = choice_to_explanation

    for key in d:
        print '\t'+key + ': '+d[key]
    prompt = '/'.join(d.keys())+'? '

    first = True
    choice = ''
    while first or choice not in d.keys():
        if not first:
            print 'unrecognized choice'
        first = False
        choice = raw_input(prompt)
    return choice


def float32_floatX(f):
    """
    This function changes floatX to float32 for the call to f. Useful in GPU
    tests.

    Parameters
    ----------
    f : WRITEME

    Returns
    -------
    WRITEME
    """
    def new_f(*args, **kwargs):
        """
        .. todo::

            WRITEME
        """
        old_floatX = theano.config.floatX
        theano.config.floatX = 'float32'
        try:
            f(*args, **kwargs)
        finally:
            theano.config.floatX = old_floatX

    # If we don't do that, tests function won't be run.
    new_f.func_name = f.func_name
    return new_f


def update_wrapper(wrapper,
                   wrapped,
                   assigned=WRAPPER_ASSIGNMENTS,
                   concatenated=WRAPPER_CONCATENATIONS,
                   append=False,
                   updated=WRAPPER_UPDATES):
    """
    A Python decorator which acts like `functools.update_wrapper` but also has
    the ability to concatenate attributes.

    Parameters
    ----------
    wrapper : functon
        Function to be updated
    wrapped : function
        Original function
    assigned : tuple, optional
        Tuple naming the attributes assigned directly from the wrapped function
        to the wrapper function. Defaults to `utils.WRAPPER_ASSIGNMENTS`.
    concatenated : tuple, optional
        Tuple naming the attributes from the wrapped function concatenated with
        the ones from the wrapper function. Defaults to
        `utils.WRAPPER_CONCATENATIONS`.
    append : bool, optional
        If True, appends wrapped attributes to wrapper attributes instead of
        prepending them. Defaults to False.
    updated : tuple, optional
        Tuple naming the attributes of the wrapper that are updated with the
        corresponding attribute from the wrapped function. Defaults to
        `functools.WRAPPER_UPDATES`.

    Returns
    -------
    wrapper : function
        Updated wrapper function

    Notes
    -----
    This can be used to concatenate the wrapper's docstring with the wrapped's
    docstring and should help reduce the ammount of documentation to write: one
    can use this decorator on child classes' functions when their
    implementation is similar to the one of the parent class. Conversely, if a
    function defined in a child class departs from its parent's implementation,
    one can simply explain the differences in a 'Notes' section without
    re-writing the whole docstring.
    """
    for attr in assigned:
        setattr(wrapper, attr, getattr(wrapped, attr))
    for attr in concatenated:
        # Make sure attributes are not None
        if getattr(wrapped, attr) is None:
            setattr(wrapped, attr, "")
        if getattr(wrapper, attr) is None:
            setattr(wrapper, attr, "")
        if append:
            setattr(wrapper,
                    attr,
                    getattr(wrapped, attr) + getattr(wrapper, attr))
        else:
            setattr(wrapper,
                    attr,
                    getattr(wrapper, attr) + getattr(wrapped, attr))
    for attr in updated:
        getattr(wrapper, attr).update(getattr(wrapped, attr, {}))
    # Return the wrapper so this can be used as a decorator via partial()
    return wrapper


def wraps(wrapped,
          assigned=WRAPPER_ASSIGNMENTS,
          concatenated=WRAPPER_CONCATENATIONS,
          append=False,
          updated=WRAPPER_UPDATES):
    """
    Decorator factory to apply `update_wrapper()` to a wrapper function

    Returns a decorator that invokes `update_wrapper()` with the decorated
    function as the wrapper argument and the arguments to `wraps()` as the
    remaining arguments. Default arguments are as for `update_wrapper()`.
    This is a convenience function to simplify applying `partial()` to
    `update_wrapper()`.

    Examples
    --------
    >>> class Parent(object):
    ...     def f(x):
    ...        '''
    ...        Adds 1 to x
    ...
    ...        Parameters
    ...        ----------
    ...        x : int
    ...            Variable to increment by 1
    ...
    ...        Returns
    ...        -------
    ...        rval : int
    ...            x incremented by 1
    ...        '''
    ...        rval = x + 1
    ...        return rval
    ...
    >>> class Child(Parent):
    ...     @wraps(Parent.f)
    ...     def f(x):
    ...        '''
    ...        Notes
    ...        -----
    ...        Also prints the incremented value
    ...        '''
    ...        rval = x + 1
    ...        print rval
    ...        return rval
    ...
    >>> c = Child()
    >>> print c.f.__doc__

        Adds 1 to x

        Parameters
        ----------
        x : int
            Variable to increment by 1

        Returns
        -------
        rval : int
           x incremented by 1

        Notes
        -----
        Also prints the incremented value
    """
    return partial(update_wrapper, wrapped=wrapped, assigned=assigned,
                   append=append,updated=updated)
