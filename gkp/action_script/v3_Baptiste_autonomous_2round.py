# -*- coding: utf-8 -*-
"""
Created on Wed Apr  8 13:27:08 2020

@author: Vladimir Sivak
"""

import tensorflow as tf
from numpy import sqrt, pi



delta = 0.0
eps = 0.33

period = 2

b_amp = 2*sqrt(pi)

### Script of actions
script = {
    'alpha' : [delta+0j, -1j*delta],
    'beta'  : [b_amp+0j, 1j*b_amp],
    'epsilon' : [-1j*eps, eps+0j],
    'phi' : [pi/2, pi/2]
    }

# Mask 1 allows the ActionWrapper to use the learned value of the action on
# that time step, while 0 allows to use the scripted value.
mask = {
    'alpha' : [1, 1],
    'beta'  : [0, 0],
    'epsilon' : [1, 1],
    'phi' : [0, 0]
    }