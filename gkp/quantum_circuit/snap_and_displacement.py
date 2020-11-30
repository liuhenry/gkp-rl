# -*- coding: utf-8 -*-
"""
Created on Wed Oct 28 20:19:56 2020

@author: Vladimir Sivak
"""
import tensorflow as tf
from gkp.gkp_tf_env.gkp_tf_env import GKP
from gkp.gkp_tf_env import helper_functions as hf
from tf_agents import specs
from simulator.hilbert_spaces import Oscillator, OscillatorQubit

class QuantumCircuit(Oscillator, GKP):
    """
    Universal gate sequence for open-loop unitary control of the oscillator
    in the large-chi regime. 
    
    The gate sequence consists of 
        1) oscillator displacement
        2) selective number-dependent arbitrary phase (SNAP) gate
        3) reverse oscillator displacement
    
    """
    def __init__(
        self,
        *args,
        # Required kwargs
        t_gate,
        # Optional kwargs
        **kwargs):
        """
        Args:
            t_gate (float): Gate time in seconds.
        """
        self.t_gate = tf.constant(t_gate, dtype=tf.float32)
        self.step_duration = self.t_gate
        super().__init__(*args, **kwargs)

    @property
    def _quantum_circuit_spec(self):
        spec = {'alpha' : specs.TensorSpec(shape=[2], dtype=tf.float32),
                'theta' : specs.TensorSpec(shape=[14], dtype=tf.float32)}
        return spec

    @tf.function
    def _quantum_circuit(self, psi, action):
        """
        Args:
            psi (Tensor([batch_size,N], c64)): batch of states
            action (dict, 'alpha' : Tensor([batch_size,2], tf.float32),
                          'theta' : Tensor([batch_size,14], tf.float32))

        Returns: see parent class docs

        """
        # Extract parameters
        alpha = hf.vec_to_complex(action['alpha'])
        theta = action['theta']

        # Build gates
        displace = self.displace(alpha)
        snap = self.snap(theta)

        # Apply gates
        psi = displace.matvec(psi)
        psi = snap.matvec(psi)
        psi = displace.adjoint().matvec(psi)

        return psi, psi, tf.ones((self.batch_size,1))

