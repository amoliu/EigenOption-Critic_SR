# Copyright 2017 The TensorFlow Agents Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Example configurations using the PPO algorithm."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# pylint: disable=unused-variable

from agents import A3CSFAgent
from agents import DQNSFAgent, DQNSF_ONEHOT_Agent
from env_wrappers import GridWorld
import functools
import networks


def default():
  """Default configuration for PPO."""
  num_agents = 8
  eval_episodes = 1
  use_gpu = False
  max_length = 10000000
  return locals()

def a3c_sf_4rooms():
  locals().update(default())
  agent = A3CSFAgent
  agent_type = "a3c"
  num_agents = 8
  use_gpu = False
  nb_options = 4
  # Network
  network = networks.NNSFNetwork
  weight_summaries = dict(
      all=r'.*',
      conv=r'.*/conv/.*',
      fc=r'.*/fc/.*',
      term=r'.*/option_term/.*',
      q_val=r'.*/q_val/.*',
      policy=r'.*/i_o_policies/.*')

  conv_layers = (5, 2, 32),
  input_size = (13, 13)
  history_size = 3
  fc_layers = 32, 64,
  sf_layers = 64, 32, 64
  aux_fc_layers = 64, 32
  aux_deconv_layers = (5, 2, 0, 32), (5, 2, 0, 3),
  # Optimization
  network_optimizer = 'AdamOptimizer'
  # lr = 0.0007
  lr = 1e-5
  discount = 0.985
  entropy_coef = 1e-4
  critic_coef = 0.5
  sf_coef = 1
  instant_r_coef = 1
  option_entropy_coef = 0.01
  aux_coef = 1

  env = functools.partial(
    GridWorld, "../mdps/4rooms.mdp")
  max_update_freq = 30
  min_update_freq = 5
  steps = 1e6   # 1M
  training_steps = 5e5
  explore_steps = 1e5
  final_random_action_prob = 0.1
  initial_random_action_prob = 1.0
  delib_cost = 0
  margin_cost = 0
  gradient_clip_value = 40
  summary_interval = 10
  checkpoint_interval = 1
  eval_interval = 1
  policy_steps = 1e3
  # sf_transition_matrix_steps = 50000#e3
  # sf_transition_options_steps = 50000#e3
  sf_transition_matrix_size = 50000

  return locals()

def dqn_sf_4rooms():
  locals().update(default())
  agent = DQNSFAgent
  agent_type = "dqn"
  num_agents = 1
  use_gpu = True
  # Network
  network = networks.DQNSFNetwork
  weight_summaries = dict(
      all=r'.*',
      conv=r'.*/conv/.*',
      fc=r'.*/fc/.*',
      term=r'.*/option_term/.*',
      q_val=r'.*/q_val/.*',
      policy=r'.*/i_o_policies/.*')

  conv_layers = (5, 2, 32),
  input_size = (13, 13)
  history_size = 3
  fc_layers = 32, 64,
  sf_layers = 64, 32, 64
  aux_fc_layers = 64, 32
  aux_deconv_layers = (5, 2, 0, 32), (5, 2, 0, 3),
  # Optimization
  network_optimizer = 'AdamOptimizer'
  # lr = 0.0007
  lr = 1e-5
  discount = 0.985
  entropy_coef = 1e-4
  sf_coef = 1
  aux_coef = 1

  env = functools.partial(
    GridWorld, "../mdps/4rooms.mdp")

  observation_steps = 500000
  training_steps = 10 * observation_steps
  steps = observation_steps + training_steps
  sf_matrix_size = 50000
  target_update_freq = 1000
  batch_size = 100

  # final_random_action_prob = 0.1
  # initial_random_action_prob = 1.0
  gradient_clip_value = 40
  summary_interval = 100000
  checkpoint_interval = 100000
  eval_interval = 1
  return locals()

def dqn_sf_4rooms_net_with_options():
  locals().update(default())
  agent = DQNSFAgent
  agent_type = "dqn"
  num_agents = 1
  use_gpu = True
  # Network
  network = networks.DQNSFNetwork
  weight_summaries = dict(
      all=r'.*',
      conv=r'.*/conv/.*',
      fc=r'.*/fc/.*',
      term=r'.*/option_term/.*',
      q_val=r'.*/q_val/.*',
      policy=r'.*/i_o_policies/.*')

  conv_layers = (5, 2, 32),
  input_size = (13, 13)
  history_size = 3
  fc_layers = 32, 64,
  sf_layers = 64, 32, 64
  aux_fc_layers = 64, 32
  aux_deconv_layers = (5, 2, 0, 32), (5, 2, 0, 3),
  # Optimization
  network_optimizer = 'RMSPropOptimizer'
  # lr = 0.0007
  lr = 1e-4
  discount = 0.9
  entropy_coef = 1e-4
  sf_coef = 1
  aux_coef = 1

  env = functools.partial(
    GridWorld, "../mdps/4rooms.mdp")

  observation_steps = 500000
  training_steps = 4900000
  steps = observation_steps + training_steps
  sf_matrix_size = 50000
  target_update_freq = 1000
  batch_size = 32
  option_steps = 100000
  option_observation_steps = 10000
  option_explore_steps = 1000
  final_random_action_prob = 0.1
  initial_random_action_prob = 1.0

  # final_random_action_prob = 0.1
  # initial_random_action_prob = 1.0
  gradient_clip_value = 40
  summary_interval = 100000
  checkpoint_interval = 100000
  eval_interval = 1
  option_update_freq = 100
  option_batch_size = 100
  option_memory_size = 50000
  option_summary_interval = 1000
  option_checkpoint_interval = 1000

  return locals()

def dqn_sf_4rooms_fc():
  locals().update(default())
  agent = DQNSFAgent
  agent_type = "dqn"
  num_agents = 1
  use_gpu = True
  # Network
  network = networks.DQNSF_FCNetwork
  weight_summaries = dict(
      all=r'.*',
      conv=r'.*/conv/.*',
      fc=r'.*/fc/.*',
      term=r'.*/option_term/.*',
      q_val=r'.*/q_val/.*',
      policy=r'.*/i_o_policies/.*')

  conv_layers = (5, 2, 32),
  input_size = (13, 13)
  history_size = 3
  fc_layers = 2028,
  sf_layers = 2028,
  aux_fc_layers = 507,
  aux_deconv_layers = (5, 2, 0, 32), (5, 2, 0, 3),
  # Optimization
  network_optimizer = 'RMSPropOptimizer'
  # lr = 0.0007
  lr = 1e-4
  discount = 0.9
  entropy_coef = 1e-4
  sf_coef = 1
  aux_coef = 1

  env = functools.partial(
    GridWorld, "../mdps/4rooms.mdp")

  observation_steps = 500000
  training_steps = 10000000
  steps = observation_steps + training_steps
  sf_matrix_size = 50000
  target_update_freq = 1000
  batch_size = 32
  option_steps = 100000
  option_observation_steps = 10000
  option_explore_steps = 1000
  final_random_action_prob = 0.1
  initial_random_action_prob = 1.0

  # final_random_action_prob = 0.1
  # initial_random_action_prob = 1.0
  gradient_clip_value = 40
  summary_interval = 100000
  checkpoint_interval = 100000
  eval_interval = 1
  option_update_freq = 100
  option_batch_size = 100
  option_memory_size = 50000
  option_summary_interval = 1000
  option_checkpoint_interval = 1000
  return locals()

def dqn_sf_4rooms_fc2():
  locals().update(default())
  agent = DQNSFAgent
  agent_type = "dqn"
  num_agents = 1
  use_gpu = True
  # Network
  network = networks.DQNSF_FCNetwork
  weight_summaries = dict(
      all=r'.*',
      conv=r'.*/conv/.*',
      fc=r'.*/fc/.*',
      term=r'.*/option_term/.*',
      q_val=r'.*/q_val/.*',
      policy=r'.*/i_o_policies/.*')

  input_size = (13, 13)
  history_size = 3
  fc_layers = 128,
  sf_layers = 128,
  aux_fc_layers = 507,
  feat_decay = 0
  sf_weight_decay = 0
  network_optimizer = 'AdamOptimizer'
  lr = 1e-3
  discount = 0.985
  state_uniform_walk = False
  sf_coef = 1
  aux_coef = 1

  env = functools.partial(
    GridWorld, "../mdps/4rooms.mdp")

  observation_steps = 500000
  training_steps = 5000000
  steps = observation_steps + training_steps
  sf_matrix_size = 50000
  target_update_freq = 16 * 100
  batch_size = 16

  final_random_action_prob = 0.1
  initial_random_action_prob = 1.0

  gradient_clip_value = 40
  summary_interval = 100000
  checkpoint_interval = 100000

  return locals()

def dqn_sf_4rooms_onehot():
  locals().update(default())
  agent = DQNSF_ONEHOT_Agent
  agent_type = "dqn"
  num_agents = 1
  use_gpu = True
  # Network
  network = networks.DQNSF_ONEHOT_Network
  weight_summaries = dict(
      all=r'.*',
      conv=r'.*/conv/.*',
      fc=r'.*/fc/.*',
      term=r'.*/option_term/.*',
      q_val=r'.*/q_val/.*',
      policy=r'.*/i_o_policies/.*')

  input_size = (13, 13)
  history_size = 3
  sf_layers = 169,
  # Optimization
  network_optimizer = 'AdamOptimizer'
  # lr = 0.0007
  lr = 1e-3
  discount = 0.985
  entropy_coef = 1e-4
  sf_coef = 1
  aux_coef = 1

  env = functools.partial(
    GridWorld, "../mdps/4rooms.mdp")

  observation_steps = 500000
  training_steps = 5000000
  steps = observation_steps + training_steps
  sf_matrix_size = 50000
  target_update_freq = 32
  batch_size = 32
  option_steps = 10000
  option_observation_steps = 1000
  option_explore_steps = 100
  final_random_action_prob = 0.1
  initial_random_action_prob = 1.0

  # final_random_action_prob = 0.1
  # initial_random_action_prob = 1.0
  gradient_clip_value = 40
  summary_interval = 10000
  checkpoint_interval = 10000
  eval_interval = 1
  option_update_freq = 100
  option_batch_size = 100
  option_memory_size = 50000
  option_summary_interval = 1000
  option_checkpoint_interval = 1000
  return locals()