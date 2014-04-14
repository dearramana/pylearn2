import unittest
import numpy as np
from pylearn2.datasets.tl_challenge import TL_Challenge
from pylearn2.space import Conv2DSpace
from pylearn2.testing.skip import skip_if_no_data


class TestTL_Challenge(unittest.TestCase):
    def setUp(self):
        skip_if_no_data()
        self.train = TL_Challenge(which_set='train')
        self.unlabeled = TL_Challenge(which_set='unlabeled')
        self.test = TL_Challenge(which_set='test')

    def test_topo(self):
        """Tests that a topological batch has 4 dimensions"""
        topo = self.train.get_batch_topo(1)
        assert topo.ndim == 4
