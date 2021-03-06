# -*- coding: utf-8 -*-
"""
Created on Fri Oct 30 18:13:41 2020

@author: Vladimir Sivak
"""

import os
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"]='true'
os.environ["CUDA_VISIBLE_DEVICES"]="0"

# append parent 'gkp-rl' directory to path 
import sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), os.pardir)))

import qutip as qt
import tensorflow as tf
import numpy as np
from math import sqrt, pi
from gkp.agents import PPO
from tf_agents.networks import actor_distribution_network
from gkp.agents import actor_distribution_network_gkp
from gkp.gkp_tf_env import helper_functions as hf

"""
Train PPO agent to do Fock state N=10 preparation with universal gate sequence
consisting of SNAP gates and oscillator displacements.

The episodes start from vacuum, and photon number measurements are performed 
in the end to assign reward.

"""

root_dir = r'E:\data\gkp_sims\PPO\examples\SNAP_with_feedback_comparison_v4\t=3.40'
root_dir = os.path.join(root_dir,'0')

# Params for environment
env_kwargs = {
    'simulate' : 'snap_and_displacement_angle_phase',
    'init' : 'vac',
    'H' : 1,
    'T' : 5, 
    'attn_step' : 1,
    'N' : 50}

# Params for reward function
target_state = qt.tensor(qt.basis(2,0), qt.basis(50,3))

# reward_kwargs = {'reward_mode' : 'tomography',
#                   'tomography' : 'wigner',
#                   'target_state' : target_state,
#                   'window_size' : 12,
#                   'sample_from_buffer' : True,
#                   'buffer_size' : 5000
#                   }

reward_kwargs = {'reward_mode' : 'Fock',
                  'target_state' : target_state
                  }

reward_kwargs_eval = {'reward_mode' : 'overlap',
                      'target_state' : target_state
                      }

# Params for action wrapper
action_script = 'snap_and_displacements_angle_phase'
action_scale = {'alpha':4, 'theta':pi, 'phi':pi}
to_learn = {'alpha':True, 'theta':True, 'phi':pi}

train_batch_size = 1000
eval_batch_size = 1000

train_episode_length = lambda x: 5
eval_episode_length = lambda x: 5

# Create drivers for data collection
from gkp.agents import dynamic_episode_driver_sim_env

collect_driver = dynamic_episode_driver_sim_env.DynamicEpisodeDriverSimEnv(
    env_kwargs, reward_kwargs, train_batch_size, 
    action_script, action_scale, to_learn, train_episode_length)

eval_driver = dynamic_episode_driver_sim_env.DynamicEpisodeDriverSimEnv(
    env_kwargs, reward_kwargs_eval, eval_batch_size, 
    action_script, action_scale, to_learn, eval_episode_length)

PPO.train_eval(
        root_dir = root_dir,
        random_seed = 0,
        num_epochs = 5000,
        # Params for train
        normalize_observations = True,
        normalize_rewards = False,
        discount_factor = 1.0,
        lr = 1e-3,
        lr_schedule = lambda x: 1e-3 if x<500 else 1e-4,
        num_policy_updates = 20,
        initial_adaptive_kl_beta = 0.0,
        kl_cutoff_factor = 0,
        importance_ratio_clipping = 0.1,
        value_pred_loss_coef = 0.005,
        gradient_clipping = 1.0,
        # Params for log, eval, save
        eval_interval = 100,
        save_interval = 100,
        checkpoint_interval = 10000,
        summary_interval = 100,
        # Params for data collection
        train_batch_size = train_batch_size,
        eval_batch_size = eval_batch_size,
        collect_driver = collect_driver,
        eval_driver = eval_driver,
        replay_buffer_capacity = 7000,
        # Policy and value networks
        ActorNet = actor_distribution_network_gkp.ActorDistributionNetworkGKP,
        actor_fc_layers = (),
        value_fc_layers = (),
        use_rnn = True,
        actor_lstm_size = (12,),
        value_lstm_size = (12,)
        )