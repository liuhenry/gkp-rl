# -*- coding: utf-8 -*-
"""
Created on Mon Nov 23 22:38:34 2020

@author: Vladimir Sivak
"""
import tensorflow as tf
from tensorflow import complex64 as c64
from math import sqrt
from simulator.utils import tensor

from distutils.version import LooseVersion
if LooseVersion(tf.__version__) >= "2.2":
    diag = tf.linalg.diag
else:
    import numpy as np
    diag = np.diag  # k=1 option is broken in tf.linalg.diag in TF 2.1 (#35761)

"""
Operators are wrapped as instances of tf.linalg.LinearOperator which gives 
access to a powerful API with a whole bunch of useful features, such as:

Attributes: shape, batch_shape, domain_dimension, is_self_adjoint, ...

Methods: adjoint, to_dense, eigvals, matmul, matvec, inverse, ...

More detailed documentation:
    https://www.tensorflow.org/api_docs/python/tf/linalg/LinearOperator

States are represented as simple c64 batched tensors of shape=[B1, .., Bb, N].

Example 1:
    
    I = identity(2) # identity on the qubit
    a_dag = create(100) # creation operator on the oscillator
    # construct an operator on a joint Hilbert space and act with it on vacuum
    fock1 = tf.linalg.LinearOperatorKronecker([I, a_dag]).matvec(vac)

Example 2:
    # Normalize states like so: 
    normalized_state, norm = normalize(state)
    
"""

# TODO: maybe re-define matvec to include explicit normalization
# TODO: have different decorators for batched and un-batched operators
# TODO: add is_self_adjoint attribute to be passed to the wrapper
def linear_operator(func):
    """
    Wrap the output of <func> into tf.linalg.LinearOperator object.
    
    """
    def wrapper(*args, **kwargs):
        name = kwargs['name'] if 'name' in kwargs.keys() else func.__name__
        operator_matrix = func(*args, **kwargs)
        return tf.linalg.LinearOperatorFullMatrix(
            operator_matrix, is_square=True, name=name)
    return wrapper

### Constant operators

@linear_operator
def sigma_x():
    return tf.constant([[0., 1.], [1., 0.]], dtype=c64)


@linear_operator
def sigma_y():
    return tf.constant([[0.j, -1.j], [1.j, 0.j]], dtype=c64)


@linear_operator
def sigma_z():
    return tf.constant([[1., 0.], [0., -1.]], dtype=c64)


@linear_operator
def sigma_m():
    return tf.constant([[0., 1.], [0., 0.]], dtype=c64)


@linear_operator
def hadamard():
    return 1/sqrt(2) * tf.constant([[1., 1.], [1., -1.]], dtype=c64)


@linear_operator
def identity(N):
    """Returns an identity operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN identity operator
    """
    return tf.eye(N, dtype=c64)


@linear_operator
def destroy(N):
    """Returns a destruction (lowering) operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN creation operator
    """
    a = diag(tf.sqrt(tf.range(1, N, dtype=tf.float32)), k=1)
    return tf.cast(a, dtype=c64)


@linear_operator
def create(N):
    """Returns a creation (raising) operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN creation operator
    """
    return destroy(N).adjoint().to_dense()


@linear_operator
def num(N):
    """Returns the number operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN number operator
    """
    return tf.cast(diag(tf.range(0, N)), dtype=c64)


@linear_operator
def position(N):
    """Returns the position operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN position operator
    """
    # Preserve max precision in intermediate calculations until final cast
    sqrt2 = tf.sqrt(tf.constant(2, dtype=c64))
    a_dag = create(N).to_dense()
    a = destroy(N).to_dense()
    return tf.cast((a_dag + a) / sqrt2, dtype=c64)


@linear_operator
def momentum(N):
    """Returns the momentum operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN momentum operator
    """
    # Preserve max precision in intermediate calculations until final cast
    sqrt2 = tf.sqrt(tf.constant(2, dtype=c64))
    a_dag = create(N).to_dense()
    a = destroy(N).to_dense()
    return tf.cast(1j * (a_dag - a) / sqrt2, dtype=c64)


@linear_operator
def parity(N):
    """Returns the photon number parity operator in the Fock basis.

    Args:
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN photon number parity operator
    """
    pm1 = tf.where(tf.math.floormod(tf.range(N),2)==1, -1, 1)
    return diag(tf.cast(pm1, dtype=c64))

@linear_operator
def projector(n, N):
    """
    Returns a projector onto n-th basis state in N-dimensional Hilbert space.

    Args:
        n (int): index of basis vector
        N (int): Dimension of Hilbert space

    Returns:
        Tensor([N, N], tf.complex64): NxN photon number parity operator
    """
    assert n < N
    return diag(tf.one_hot(n, N, dtype=c64))


### Parametrized operators

class ParametrizedOperator():
    
    def __init__(self, N, tensor_with=None, name=None):
        """
        Args:
            N (int): dimension of Hilbert space
            tensor_with (list, LinearOperator): a list of operators to compute
                tensor product. By convention, <None> should be used in place
                of this operator in the list. For example, [identity(2), None] 
                will create operator in the Hilbert space of size 2*N acting
                trivially on the first component in the tensor product.
            name (str, optional): name of LinearOperator instance

        """
        self.N = N
        self.tensor_with = tensor_with
        self.name = name if name else self.__class__.__name__

    def __call__(self, *args, **kwargs):
        kwargs['name'] = self.name
        this_op = self.compute(*args, **kwargs)
        if self.tensor_with is not None:
            ops = [T if T is not None else this_op for T in self.tensor_with]
            return tensor(ops)
        else:
            return this_op

    @linear_operator
    @tf.function  
    def compute(self, *args, **kwargs):
        return self._compute(*args, **kwargs)
    
    def _compute(self):
        """Subclasses need to implement this."""


class TranslationOperator(ParametrizedOperator):
    """ 
    Translation in phase space.
    
    Example:
        T = TranslationOperator(100)
        alpha = tf.constant([1.23+0.j, 3.56j, 2.12+1.2j])
        T(alpha) # shape=[3,100,100]
        state = T(alpha).matvec(state)
    """
    
    def __init__(self, N, *args, **kwargs):
        """ Pre-diagonalize position and momentum operators."""
        p = momentum(N).to_dense()
        q = position(N).to_dense()
        
        # Pre-diagonalize
        (self._eig_q, self._U_q) = tf.linalg.eigh(q)
        (self._eig_p, self._U_p) = tf.linalg.eigh(p)
        self._qp_comm = tf.linalg.diag_part(q @ p - p @ q)
        super().__init__(N=N, *args, **kwargs)

    def _compute(self, amplitude, *args, **kwargs):
        """Calculates T(amplitude) for a batch of amplitudes using BCH.

        Args:
            amplitude (Tensor([B1, ..., Bb], c64)): A batch of amplitudes

        Returns:
            Tensor([B1, ..., Bb, N, N], c64): A batch of T(amplitude)
        """
        # Reshape amplitude for broadcast against diagonals
        amplitude = tf.cast(tf.expand_dims(amplitude, -1), dtype=c64)

        # Take real/imag of amplitude for the commutator part of the expansion
        re_a = tf.cast(tf.math.real(amplitude), dtype=c64)
        im_a = tf.cast(tf.math.imag(amplitude), dtype=c64)

        # Exponentiate diagonal matrices
        expm_q = tf.linalg.diag(tf.math.exp(1j * im_a * self._eig_q))
        expm_p = tf.linalg.diag(tf.math.exp(-1j * re_a * self._eig_p))
        expm_c = tf.linalg.diag(tf.math.exp(-0.5 * re_a * im_a * self._qp_comm))

        # Apply Baker-Campbell-Hausdorff
        return tf.cast(
            self._U_q
            @ expm_q
            @ tf.linalg.adjoint(self._U_q)
            @ self._U_p
            @ expm_p
            @ tf.linalg.adjoint(self._U_p)
            @ expm_c,
            dtype=c64,
        )


class DisplacementOperator(TranslationOperator):
    """ 
    Displacement in phase space D(amplitude) = T(amplitude * sqrt(2)).
    
    """    
    def __call__(self, amplitude, *args, **kwargs):
        sqrt2 = tf.math.sqrt(tf.constant(2, dtype=amplitude.dtype))
        return super().__call__(amplitude*sqrt2, *args, **kwargs)


class RotationOperator(ParametrizedOperator):
    """ Rotation in phase space."""    

    def _compute(self, phase, *args, **kwargs):
        """Calculates R(phase) = e^{-i*phase*n} for a batch of phases.

        Args:
            phase (Tensor([B1, ..., Bb], c64)): A batch of phases

        Returns:
            Tensor([B1, ..., Bb, N, N], c64): A batch of R(phase)
        """
        phase = tf.cast(tf.expand_dims(phase, -1), dtype=c64)
        exp_diag = tf.math.exp(phase * tf.cast(tf.range(self.N), c64))
        return tf.linalg.diag(exp_diag)


class SNAP(ParametrizedOperator):
    """
    Selective Number-dependent Arbitrary Phase (SNAP) gate.
    SNAP(theta) = sum_n( e^(i*theta_n) * |n><n| )
    
    """          
    def _compute(self, theta, *args, **kwargs):
        """Calculates ideal SNAP(theta) for a batch of SNAP parameters.

        Args:
            theta (Tensor([B1, ..., Bb, S], c64)): A batch of parameters.

        Returns:
            Tensor([B1, ..., Bb, N, N], c64): A batch of SNAP(theta)
        """
        S = theta.shape[-1] # SNAP truncation
        D = len(theta.shape)-1
        paddings = tf.constant([[0,0]]*D + [[0,self.N-S]])
        theta = tf.cast(theta, dtype=c64)
        theta = tf.pad(theta, paddings)
        exp_diag = tf.math.exp(1j*theta)
        return tf.linalg.diag(exp_diag)
    

class QubitRotationXY(ParametrizedOperator):
    """
    Qubit rotation in xy plane.
    R(angle, phase) = e^(-i*angle/2*[cos(phase)*sx + sin(phase*sy]))
    
    """
    def __init__(self):
        super().__init__(N=2)

    def _compute(self, angle, phase, *args, **kwargs):
        """Calculates rotation matrix for a batch of rotation angles.

        Args:
            angle (Tensor([B1, ..., Bb], float32)): batched angle of rotation
                in radians, i.e. angle=pi corresponds to full qubit flip.
            phase (Tensor([B1, ..., Bb], float32)): batched axis of rotation
                in radians, where by convention 0 is x axis.

        Returns:
            Tensor([B1, ..., Bb, 2, 2], c64): A batch of R(angle, phase)
        """
        assert angle.shape == phase.shape
        angle = tf.cast(tf.reshape(angle, angle.shape+[1,1]), c64)
        phase = tf.cast(tf.reshape(phase, phase.shape+[1,1]), c64)
        
        sx = sigma_x().to_dense()
        sy = sigma_y().to_dense()
        I = identity(2).to_dense()
        
        R = tf.math.cos(angle/2) * I - 1j*tf.math.sin(angle/2) * \
            (tf.math.cos(phase)*sx + tf.math.sin(phase)*sy)
        return R


class Phase(ParametrizedOperator):
    """ Simple phase factor."""
    def _compute(self, angle, *args, **kwargs):
        """
        Calculates batch phase factor e^(i*angle)

        Args:
            angle (Tensor([B1, ..., Bb], float32)): batch of angles in radians
            
        Returns:
            Tensor([B1, ..., Bb, N, N], c64): A batch of phase factors
        """
        angle = tf.cast(tf.reshape(angle, angle.shape+[1,1]), c64)
        return tf.math.exp(1j*angle) * tf.eye(self.N, dtype=c64)


class NumericalCoefficient(ParametrizedOperator):
    """ Simple numerical coefficient."""
    def _compute(self, coef, *args, **kwargs):
        return tf.cast(coef, c64) * tf.eye(self.N, dtype=c64)
    
