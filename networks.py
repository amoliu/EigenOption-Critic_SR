from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import tensorflow.contrib.layers as layers
from utility import gradient_summaries, huber_loss
import numpy as np
from agents.schedules import LinearSchedule, TFLinearSchedule
import os

class LinearSFNetwork():
  def __init__(self, scope, config, action_size, nb_states):
    self._scope = scope
    self._conv_layers = config.conv_layers
    self._fc_layers = config.fc_layers
    self._action_size = action_size
    self._nb_options = config.nb_options
    self._nb_envs = config.num_agents
    self._config = config
    self.option = 0
    self._sf_layers = config.sf_layers
    self._deconv_layers = config.deconv_layers
    self._network_optimizer = config.network_optimizer(
      self._config.lr, name='network_optimizer')

    with tf.variable_scope(scope):
      self.observation = tf.placeholder(shape=[None, nb_states],
                                        dtype=tf.float32, name="Inputs")
      self.sf = layers.fully_connected(self.observation, num_outputs=nb_states,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="sf")
      if scope != 'global':
        # self.actions_placeholder = tf.placeholder(shape=[None], dtype=tf.int32, name="Actions")
        # self.actions_onehot = tf.one_hot(self.actions_placeholder, self._action_size, dtype=tf.float32,
        #                                  name="Actions_Onehot")
        self.target_sf = tf.placeholder(shape=[None, nb_states], dtype=tf.float32, name="target_SF")

        with tf.name_scope('sf_loss'):
          sf_td_error = self.target_sf - self.sf
          self.sf_loss = tf.reduce_mean(tf.square(sf_td_error))

        self.loss = self.sf_loss  # + self.instant_r_loss
        loss_summaries = [tf.summary.scalar('avg_sf_loss', self.sf_loss)]

        local_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope)
        gradients = tf.gradients(self.loss, local_vars)
        self.var_norms = tf.global_norm(local_vars)
        grads, self.grad_norms = tf.clip_by_global_norm(gradients, self._config.gradient_clip_value)

        # for grad, weight in zip(grads, local_vars):
        #   if grad is not None:
        #     self.summaries.append(tf.summary.histogram(weight.name + '_grad', grad))
        #     self.summaries.append(tf.summary.histogram(weight.name, weight))

        self.merged_summary = tf.summary.merge(loss_summaries + [
          tf.summary.scalar('gradient_norm', tf.global_norm(gradients)),
          tf.summary.scalar('cliped_gradient_norm', tf.global_norm(grads)),
          gradient_summaries(zip(grads, local_vars))])
        global_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'global')
        self.apply_grads = self._network_optimizer.apply_gradients(zip(grads, global_vars))


class DIFNetwork():
  def __init__(self, scope, config, action_size, nb_states):
    self._scope = scope
    # self.option = 0
    self._conv_layers = config.conv_layers
    self._fc_layers = config.fc_layers
    self._sf_layers = config.sf_layers
    self._aux_fc_layers = config.aux_fc_layers
    self._aux_deconv_layers = config.aux_deconv_layers
    self._action_size = action_size
    self._nb_options = config.nb_options
    self._nb_envs = config.num_agents
    self._config = config

    self._network_optimizer = config.network_optimizer(
      self._config.lr, name='network_optimizer')

    with tf.variable_scope(scope):
      self.observation = tf.placeholder(shape=[None, config.input_size[0], config.input_size[1], config.history_size],
                                        dtype=tf.float32, name="Inputs")
      self.image_summaries = []
      if self._config.history_size == 3:
        self.image_summaries.append(tf.summary.image('input', self.observation * 255, max_outputs=30))
      else:
        self.image_summaries.append(tf.summary.image('input', self.observation[:, :, :, 0:1] * 255, max_outputs=30))
      self.summaries = []

      with tf.variable_scope('conv'):
        for i, (kernel_size, stride, nb_kernels) in enumerate(self._conv_layers):
          out = layers.conv2d(self.observation, num_outputs=nb_kernels, kernel_size=kernel_size,
                              stride=stride, activation_fn=None,
                              variables_collections=tf.get_collection("variables"),
                              outputs_collections="activations", scope="conv_{}".format(i))
          # out = layer_norm_fn(out, relu=True)
          out = tf.nn.relu(out)
          self.summaries.append(tf.contrib.layers.summarize_activation(out))
        out = layers.flatten(out, scope="flatten")

      with tf.variable_scope("fc"):
        for i, nb_filt in enumerate(self._fc_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="fc_{}".format(i))

          if i < len(self._fc_layers) - 1:
            # out = layer_norm_fn(out, relu=False)
            # out = layer_norm_fn(out, relu=True)
            out = tf.nn.relu(out)
          self.summaries.append(tf.contrib.layers.summarize_activation(out))
      self.fi = out

      # out = tf.stop_gradient(layer_norm_fn(self.fi, relu=True))
      out = tf.stop_gradient(tf.nn.relu(self.fi))
      with tf.variable_scope("sf"):
        for i, nb_filt in enumerate(self._sf_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="sf_{}".format(i))
          if i < len(self._sf_layers) - 1:
            # out = layer_norm_fn(out, relu=False)
            out = tf.nn.relu(out)
          self.summaries.append(tf.contrib.layers.summarize_activation(out))

      self.sf = out

      out = self.fi
      with tf.variable_scope("action_fc"):
        self.actions_placeholder = tf.placeholder(shape=[None], dtype=tf.float32, name="Actions")
        actions = layers.fully_connected(self.actions_placeholder[..., None], num_outputs=self._fc_layers[-1],
                                         activation_fn=None,
                                         variables_collections=tf.get_collection("variables"),
                                         outputs_collections="activations", scope="action_fc{}".format(i))
      out = tf.add(out, actions)
      out = tf.nn.relu(out)

      with tf.variable_scope("aux_fc"):
        for i, nb_filt in enumerate(self._aux_fc_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="aux_fc_{}".format(i))
          if i < len(self._aux_fc_layers) - 1:
            out = tf.nn.relu(out)
          self.summaries.append(tf.contrib.layers.summarize_activation(out))

      with tf.variable_scope("aux_deconv"):
        decoder_out = tf.expand_dims(tf.expand_dims(out, 1), 1)
        for i, (kernel_size, stride, padding, nb_kernels) in enumerate(self._aux_deconv_layers):
          decoder_out = layers.conv2d_transpose(decoder_out, num_outputs=nb_kernels, kernel_size=kernel_size,
                                                stride=stride, activation_fn=None,
                                                padding="same" if padding > 0 else "valid",
                                                variables_collections=tf.get_collection("variables"),
                                                outputs_collections="activations", scope="aux_deconv_{}".format(i))
          if i < len(self._aux_deconv_layers) - 1:
            # decoder_out = layer_norm_fn(decoder_out, relu=False)
            decoder_out = tf.nn.relu(decoder_out)
          self.summaries.append(tf.contrib.layers.summarize_activation(decoder_out))

      self.next_obs = decoder_out

      if self._config.history_size == 3:
        self.image_summaries.append(tf.summary.image('next_obs', self.next_obs * 255, max_outputs=30))
      else:
        self.image_summaries.append(tf.summary.image('next_obs', self.next_obs[:, :, :, 0:1] * 255, max_outputs=30))

      if scope != 'global':
        self.target_sf = tf.placeholder(shape=[None, self._sf_layers[-1]], dtype=tf.float32, name="target_SF")
        self.target_next_obs = tf.placeholder(
          shape=[None, config.input_size[0], config.input_size[1], config.history_size], dtype=tf.float32,
          name="target_next_obs")
        if self._config.history_size == 3:
          self.image_summaries.append(tf.summary.image('target_next_obs', self.target_next_obs * 255, max_outputs=30))
        else:
          self.image_summaries.append(
            tf.summary.image('target_next_obs', self.target_next_obs[:, :, :, 0:1] * 255, max_outputs=30))
        self.matrix_sf = tf.placeholder(shape=[self._config.sf_transition_matrix_size, self._sf_layers[-1]],
                                        dtype=tf.float32, name="matrix_sf")
        self.s, self.u, self.v = tf.svd(self.matrix_sf)

        with tf.name_scope('sf_loss'):
          sf_td_error = self.target_sf - self.sf
          self.sf_loss = tf.reduce_mean(tf.square(sf_td_error))

        with tf.name_scope('aux_loss'):
          aux_error = self.next_obs - self.target_next_obs
          self.aux_loss = tf.reduce_mean(self._config.aux_coef * tf.square(aux_error))

        self.loss = self.sf_loss + self.aux_loss
        loss_summaries = [tf.summary.scalar('avg_sf_loss', self.sf_loss),
                          tf.summary.scalar('aux_loss', self.aux_loss),
                          tf.summary.scalar('total_loss', self.loss)]

        local_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope)
        gradients = tf.gradients(self.loss, local_vars)
        self.var_norms = tf.global_norm(local_vars)
        grads, self.grad_norms = tf.clip_by_global_norm(gradients, self._config.gradient_clip_value)

        self.merged_summary = tf.summary.merge(self.image_summaries + self.summaries + loss_summaries + [
          tf.summary.scalar('gradient_norm', tf.global_norm(gradients)),
          tf.summary.scalar('cliped_gradient_norm', tf.global_norm(grads)),
          gradient_summaries(zip(grads, local_vars))])
        global_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'global')
        self.apply_grads = self._network_optimizer.apply_gradients(zip(grads, global_vars))


class DIFNetwork_FC():
  def __init__(self, scope, config, action_size, nb_states):
    self._scope = scope
    # self.option = 0
    self.nb_states = nb_states
    # self.conv_layers = config.conv_layers
    self.fc_layers = config.fc_layers
    self.sf_layers = config.sf_layers
    self.aux_fc_layers = config.aux_fc_layers
    # self.aux_deconv_layers = config.aux_deconv_layers
    self.action_size = action_size
    self.nb_options = config.nb_options
    self.nb_envs = config.num_agents
    self.config = config

    self.network_optimizer = config.network_optimizer(
      self.config.lr, name='network_optimizer')

    with tf.variable_scope(scope):
      self.observation = tf.placeholder(shape=[None, config.input_size[0], config.input_size[1], config.history_size],
                                        dtype=tf.float32, name="Inputs")

      self.image_summaries = []
      self.image_summaries.append(tf.summary.image('input', self.observation, max_outputs=30))

      self.summaries_sf = []
      self.summaries_aux = []

      out = self.observation
      out = layers.flatten(out, scope="flatten")

      with tf.variable_scope("fc"):
        for i, nb_filt in enumerate(self.fc_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="fc_{}".format(i))

          if i < len(self.fc_layers) - 1:
            # out = layer_norm_fn(out, relu=True)
            out = tf.nn.relu(out)
          self.summaries_sf.append(tf.contrib.layers.summarize_activation(out))
          self.summaries_aux.append(tf.contrib.layers.summarize_activation(out))
        self.fi = out

      with tf.variable_scope("sf"):
        out = layer_norm_fn(self.fi, relu=True)
        out = tf.stop_gradient(out)
        for i, nb_filt in enumerate(self.sf_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="sf_{}".format(i))
          if i < len(self.sf_layers) - 1:
            out = tf.nn.relu(out)
          self.summaries_sf.append(tf.contrib.layers.summarize_activation(out))
        self.sf = out

      with tf.variable_scope("action_fc"):
        self.actions_placeholder = tf.placeholder(shape=[None], dtype=tf.float32, name="Actions")
        actions = layers.fully_connected(self.actions_placeholder[..., None], num_outputs=self.fc_layers[-1],
                                         activation_fn=None,
                                         variables_collections=tf.get_collection("variables"),
                                         outputs_collections="activations", scope="action_fc{}".format(i))

      with tf.variable_scope("aux_fc"):
        out = tf.add(self.fi, actions)
        # out = tf.nn.relu(out)
        for i, nb_filt in enumerate(self.aux_fc_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="aux_fc_{}".format(i))
          if i < len(self.aux_fc_layers) - 1:
            out = tf.nn.relu(out)
          self.summaries_aux.append(tf.contrib.layers.summarize_activation(out))
        self.next_obs = tf.reshape(out, (-1, config.input_size[0], config.input_size[1], config.history_size))

        self.image_summaries.append(tf.summary.image('next_obs', self.next_obs, max_outputs=30))

      if scope != 'global':
        self.target_sf = tf.placeholder(shape=[None, self.sf_layers[-1]], dtype=tf.float32, name="target_SF")
        self.target_next_obs = tf.placeholder(
          shape=[None, config.input_size[0], config.input_size[1], config.history_size], dtype=tf.float32,
          name="target_next_obs")
        self.image_summaries.append(tf.summary.image('target_next_obs', self.target_next_obs, max_outputs=30))

        self.matrix_sf = tf.placeholder(shape=[self.nb_states, self.sf_layers[-1]],
                                        dtype=tf.float32, name="matrix_sf")
        self.s, self.u, self.v = tf.svd(self.matrix_sf)

        with tf.name_scope('sf_loss'):
          sf_td_error = self.target_sf - self.sf
          self.sf_loss = tf.reduce_mean(huber_loss(sf_td_error))

        with tf.name_scope('aux_loss'):
          aux_error = self.next_obs - self.target_next_obs
          self.aux_loss = tf.reduce_mean(self.config.aux_coef * huber_loss(aux_error))

        # regularizer_features = tf.reduce_mean(self.config.feat_decay * tf.nn.l2_loss(self.fi))
        local_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope)

        gradients_sf = tf.gradients(self.sf_loss, local_vars)
        gradients_aux = tf.gradients(self.aux_loss, local_vars)
        self.var_norms = tf.global_norm(local_vars)
        grads_sf, self.grad_norms_sf = tf.clip_by_global_norm(gradients_sf, self.config.gradient_clip_value)
        grads_aux, self.grad_norms_aux = tf.clip_by_global_norm(gradients_aux, self.config.gradient_clip_value)

        self.merged_summary_sf = tf.summary.merge(
          self.summaries_sf + [tf.summary.scalar('avg_sf_loss', self.sf_loss)] + [
            tf.summary.scalar('gradient_norm_sf', tf.global_norm(gradients_sf)),
            tf.summary.scalar('cliped_gradient_norm_sf', tf.global_norm(grads_sf)),
            gradient_summaries(zip(grads_sf, local_vars))])
        self.merged_summary_aux = tf.summary.merge(self.image_summaries + self.summaries_aux +
                                                   [tf.summary.scalar('aux_loss', self.aux_loss)] + [
                                                     tf.summary.scalar('gradient_norm_sf',
                                                                       tf.global_norm(gradients_aux)),
                                                     tf.summary.scalar('cliped_gradient_norm_sf',
                                                                       tf.global_norm(grads_aux)),
                                                     gradient_summaries(zip(grads_aux, local_vars))])
        global_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'global')
        self.apply_grads_sf = self.network_optimizer.apply_gradients(zip(grads_sf, global_vars))
        self.apply_grads_aux = self.network_optimizer.apply_gradients(zip(grads_aux, global_vars))


class EignOCNetwork():
  def __init__(self, scope, config, action_size, nb_states, total_steps_tensor=None):
    self._scope = scope
    self.nb_states = nb_states
    self.fc_layers = config.fc_layers
    self.sf_layers = config.sf_layers
    self.aux_fc_layers = config.aux_fc_layers
    self.action_size = action_size
    self.nb_options = config.nb_options
    self.nb_envs = config.num_agents
    self.config = config
    self.network_optimizer = config.network_optimizer(
      self.config.lr, name='network_optimizer')
    if scope == 'global':
      self.sf_matrix_path = os.path.join(config.stage_logdir, "sf_matrix.npy")
      self.directions = np.zeros((config.nb_options, config.sf_layers[-1]))
      if os.path.exists(self.sf_matrix_path):
        self.sf_matrix_buffer = np.load(self.sf_matrix_path)
      else:
        self.sf_matrix_buffer = np.zeros(shape=(self.config.sf_matrix_size, self.config.sf_layers[-1]), dtype=np.float32)

    # self._exploration_options = TFLinearSchedule(self._config.explore_steps, self._config.final_random_action_prob,
    #                                              self._config.initial_random_action_prob)
    # if total_steps_tensor is not None:
    #   self.entropy_coef = tf.train.polynomial_decay(self.config.initial_random_action_prob, total_steps_tensor,
    #                                                 self.config.entropy_decay_steps,
    #                                                 self.config.final_random_action_prob,
    #                                                 power=0.5)
    self.entropy_coef = self.config.final_random_action_prob

    with tf.variable_scope(scope):
      self.observation = tf.placeholder(shape=[None, config.input_size[0], config.input_size[1], config.history_size],
                                        dtype=tf.float32, name="Inputs")
      self.steps = tf.placeholder(shape=[], dtype=tf.int32, name="steps")

      self.image_summaries = []
      # self.image_summaries.append(tf.summary.image('input', self.observation, max_outputs=30))

      self.summaries_sf = []
      self.summaries_aux = []
      self.summaries_option = []

      out = self.observation
      out = layers.flatten(out, scope="flatten")

      with tf.variable_scope("fi"):
        for i, nb_filt in enumerate(self.fc_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="fc_{}".format(i))

          if i < len(self.fc_layers) - 1:
            out = tf.nn.relu(out)
          self.summaries_sf.append(tf.contrib.layers.summarize_activation(out))
          self.summaries_aux.append(tf.contrib.layers.summarize_activation(out))
          self.summaries_option.append(tf.contrib.layers.summarize_activation(out))
        self.fi = out

      with tf.variable_scope("eigen_option_term"):
        out = tf.stop_gradient(tf.nn.relu(self.fi))
        self.termination = layers.fully_connected(out, num_outputs=self.nb_options,
                                                  activation_fn=tf.nn.sigmoid,
                                                  variables_collections=tf.get_collection("variables"),
                                                  outputs_collections="activations", scope="fc_option_term")
        self.summaries_option.append(tf.contrib.layers.summarize_activation(self.termination))

      with tf.variable_scope("option_q_val"):
        out = tf.stop_gradient(tf.nn.relu(self.fi))
        self.q_val = layers.fully_connected(out, num_outputs=(
          self.nb_options + self.action_size) if self.config.include_primitive_options else self.nb_options,
                                            activation_fn=None,
                                            variables_collections=tf.get_collection("variables"),
                                            outputs_collections="activations", scope="fc_q_val")
        self.summaries_option.append(tf.contrib.layers.summarize_activation(self.q_val))
        self.max_q_val = tf.reduce_max(self.q_val, 1)
        self.max_options = tf.cast(tf.argmax(self.q_val, 1), dtype=tf.int32)
        self.exp_options = tf.random_uniform(shape=[tf.shape(self.q_val)[0]], minval=0, maxval=(
          self.nb_options + self.action_size) if self.config.include_primitive_options else self.nb_options,
                                        dtype=tf.int32)
        self.local_random = tf.random_uniform(shape=[tf.shape(self.q_val)[0]], minval=0., maxval=1., dtype=tf.float32,
                                         name="rand_options")
        self.condition = self.local_random > self.config.final_random_option_prob

        self.current_option = tf.where(self.condition, self.max_options, self.exp_options)
        self.primitive_action = tf.where(self.current_option >= self.nb_options,
                                         tf.ones_like(self.current_option),
                                         tf.zeros_like(self.current_option))
        self.summaries_option.append(tf.contrib.layers.summarize_activation(self.current_option))
        self.v = tf.reduce_max(self.q_val, axis=1) * (1 - self.config.final_random_option_prob) + \
                 self.config.final_random_option_prob * tf.reduce_mean(self.q_val, axis=1)
        self.summaries_option.append(tf.contrib.layers.summarize_activation(self.v))

      if self.config.eigen:
        with tf.variable_scope("eigen_option_q_val"):
          out = tf.stop_gradient(tf.nn.relu(self.fi))
          self.eigen_q_val = layers.fully_connected(out, num_outputs=self.nb_options,
                                                    activation_fn=None,
                                                    variables_collections=tf.get_collection("variables"),
                                                    outputs_collections="activations", scope="fc_q_val")
          self.summaries_option.append(tf.contrib.layers.summarize_activation(self.eigen_q_val))
        if self.config.include_primitive_options:
          concatenated_eigen_q = tf.concat([self.q_val[:, self.config.nb_options:], self.eigen_q_val], 1)
        else:
          concatenated_eigen_q = self.eigen_q_val
        self.eigenv = tf.reduce_max(concatenated_eigen_q, axis=1) * \
                      (1 - self.config.final_random_option_prob) + \
                      self.config.final_random_option_prob * tf.reduce_mean(concatenated_eigen_q, axis=1)
        self.summaries_option.append(tf.contrib.layers.summarize_activation(self.eigenv))

      with tf.variable_scope("eigen_option_i_o_policies"):
        out = tf.stop_gradient(tf.nn.relu(self.fi))
        self.options = []
        for i in range(self.nb_options):
          option = layers.fully_connected(out, num_outputs=self.action_size,
                                          activation_fn=tf.nn.softmax,
                                          biases_initializer=None,
                                          variables_collections=tf.get_collection("variables"),
                                          outputs_collections="activations", scope="policy_{}".format(i))
          self.summaries_option.append(tf.contrib.layers.summarize_activation(option))
          self.options.append(option)
        self.options = tf.stack(self.options, 1)

      with tf.variable_scope("sf"):
        out = tf.stop_gradient(tf.nn.relu(self.fi))
        for i, nb_filt in enumerate(self.sf_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       biases_initializer=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="sf_{}".format(i))
          if i < len(self.sf_layers) - 1:
            out = tf.nn.relu(out)
          self.summaries_sf.append(tf.contrib.layers.summarize_activation(out))
        self.sf = out

      with tf.variable_scope("aux_action_fc"):
        self.actions_placeholder = tf.placeholder(shape=[None], dtype=tf.float32, name="Actions")
        actions = layers.fully_connected(self.actions_placeholder[..., None], num_outputs=self.fc_layers[-1],
                                         activation_fn=None,
                                         variables_collections=tf.get_collection("variables"),
                                         outputs_collections="activations", scope="fc_{}".format(i))

      with tf.variable_scope("aux_next_frame"):
        out = tf.add(self.fi, actions)
        # out = tf.nn.relu(out)
        for i, nb_filt in enumerate(self.aux_fc_layers):
          out = layers.fully_connected(out, num_outputs=nb_filt,
                                       activation_fn=None,
                                       variables_collections=tf.get_collection("variables"),
                                       outputs_collections="activations", scope="fc_{}".format(i))
          if i < len(self.aux_fc_layers) - 1:
            out = tf.nn.relu(out)
          self.summaries_aux.append(tf.contrib.layers.summarize_activation(out))
        self.next_obs = tf.reshape(out, (-1, config.input_size[0], config.input_size[1], config.history_size))

        # self.image_summaries.append(tf.summary.image('next_obs', self.next_obs, max_outputs=30))

      if scope != 'global':
        self.target_sf = tf.placeholder(shape=[None, self.sf_layers[-1]], dtype=tf.float32, name="target_SF")
        self.target_next_obs = tf.placeholder(
          shape=[None, config.input_size[0], config.input_size[1], config.history_size], dtype=tf.float32,
          name="target_next_obs")
        self.options_placeholder = tf.placeholder(shape=[None], dtype=tf.int32, name="options")
        self.target_eigen_return = tf.placeholder(shape=[None], dtype=tf.float32)
        self.target_return = tf.placeholder(shape=[None], dtype=tf.float32)

        self.policies = self.get_intra_option_policies(self.options_placeholder)
        self.responsible_actions = self.get_responsible_actions(self.policies, self.actions_placeholder)

        if self.config.eigen:
          eigen_q_val = self.get_eigen_q(self.options_placeholder)
        q_val = self.get_q(self.options_placeholder)
        o_term = self.get_o_term(self.options_placeholder)

        self.image_summaries.append(
          tf.summary.image('next', tf.concat([self.next_obs, self.target_next_obs], 2), max_outputs=30))

        # self.matrix_sf = tf.placeholder(shape=[self.config.sf_matrix_size, self.sf_layers[-1]],
        #                                 dtype=tf.float32, name="matrix_sf")
        if self.config.sf_matrix_size is None:
          self.config.sf_matrix_size = self.nb_states
        self.matrix_sf = tf.placeholder(shape=[self.config.sf_matrix_size, self.sf_layers[-1]],
                                        dtype=tf.float32, name="matrix_sf")
        self.eigenvalues, _, self.eigenvectors = tf.svd(self.matrix_sf)

        with tf.name_scope('sf_loss'):
          sf_td_error = self.target_sf - self.sf
        self.sf_loss = tf.reduce_mean(huber_loss(sf_td_error))

        with tf.name_scope('aux_loss'):
          aux_error = self.next_obs - self.target_next_obs
        self.aux_loss = tf.reduce_mean(self.config.aux_coef * huber_loss(aux_error))

        if self.config.eigen:
          with tf.name_scope('eigen_critic_loss'):
            eigen_td_error = self.target_eigen_return - eigen_q_val
            self.eigen_critic_loss = tf.reduce_mean(0.5 * self.config.eigen_critic_coef * tf.square(eigen_td_error))

        with tf.name_scope('critic_loss'):
          td_error = self.target_return - q_val
        self.critic_loss = tf.reduce_mean(0.5 * self.config.critic_coef * tf.square(td_error))

        with tf.name_scope('termination_loss'):
          self.term_loss = tf.reduce_mean(
            o_term * (tf.stop_gradient(q_val) - tf.stop_gradient(self.v) + 0.01))

        with tf.name_scope('entropy_loss'):
          self.entropy_loss = -self.entropy_coef * tf.reduce_mean(tf.reduce_sum(self.policies *
                                                                                tf.log(self.policies + 1e-7),
                                                                                axis=1))
        with tf.name_scope('policy_loss'):
          self.policy_loss = -tf.reduce_mean(tf.log(self.responsible_actions + 1e-7) * tf.stop_gradient(
            eigen_td_error if self.config.eigen else td_error))

        self.option_loss = self.policy_loss - self.entropy_loss + self.critic_loss + self.term_loss
        if self.config.eigen:
          self.option_loss += self.eigen_critic_loss

        local_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope)

        gradients_sf = tf.gradients(self.sf_loss, local_vars)
        gradients_aux = tf.gradients(self.aux_loss, local_vars)
        gradients_option = tf.gradients(self.option_loss, local_vars)
        gradients_primitive_option = tf.gradients(self.critic_loss, local_vars)

        self.var_norms = tf.global_norm(local_vars)
        grads_sf, self.grad_norms_sf = tf.clip_by_global_norm(gradients_sf, self.config.gradient_clip_norm_value)
        grads_aux, self.grad_norms_aux = tf.clip_by_global_norm(gradients_aux, self.config.gradient_clip_norm_value)
        grads_option, self.grad_norms_option = tf.clip_by_global_norm(gradients_option,
                                                                      self.config.gradient_clip_norm_value)
        grads_primitive_option, self.grad_norms_primitive_option = tf.clip_by_global_norm(gradients_primitive_option,
                                                                      self.config.gradient_clip_norm_value)

        self.merged_summary_sf = tf.summary.merge(
          self.summaries_sf + [tf.summary.scalar('avg_sf_loss', self.sf_loss)] + [
            tf.summary.scalar('gradient_norm_sf', tf.global_norm(gradients_sf)),
            tf.summary.scalar('cliped_gradient_norm_sf', tf.global_norm(grads_sf)),
            gradient_summaries(zip(grads_sf, local_vars))])
        self.merged_summary_aux = tf.summary.merge(self.image_summaries + self.summaries_aux +
                                                   [tf.summary.scalar('aux_loss', self.aux_loss)] + [
                                                     tf.summary.scalar('gradient_norm_aux',
                                                                       tf.global_norm(gradients_aux)),
                                                     tf.summary.scalar('cliped_gradient_norm_aux',
                                                                       tf.global_norm(grads_aux)),
                                                     gradient_summaries(zip(grads_aux, local_vars))])
        options_to_merge = self.summaries_option + [tf.summary.scalar('avg_critic_loss', self.critic_loss),
                                                    tf.summary.scalar('avg_termination_loss', self.term_loss),
                                                    tf.summary.scalar('avg_entropy_loss', self.entropy_loss),
                                                    tf.summary.scalar('avg_policy_loss', self.policy_loss),
                                                    tf.summary.scalar('gradient_norm_option',
                                                                      tf.global_norm(gradients_option)),
                                                    tf.summary.scalar('cliped_gradient_norm_option',
                                                                      tf.global_norm(grads_option)),
                                                    gradient_summaries(zip(grads_option, local_vars))]
        if self.config.eigen:
          options_to_merge += [tf.summary.scalar('avg_eigen_critic_loss', self.eigen_critic_loss)]

        self.merged_summary_option = tf.summary.merge(options_to_merge)
        global_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'global')
        self.apply_grads_sf = self.network_optimizer.apply_gradients(zip(grads_sf, global_vars))
        self.apply_grads_aux = self.network_optimizer.apply_gradients(zip(grads_aux, global_vars))
        self.apply_grads_option = self.network_optimizer.apply_gradients(zip(grads_option, global_vars))
        self.apply_grads_primitive_option = self.network_optimizer.apply_gradients(zip(grads_primitive_option, global_vars))

  def get_intra_option_policies(self, options):
    options_taken_one_hot = tf.one_hot(options, self.nb_options, dtype=tf.float32, name="options_one_hot")
    options_taken_one_hot = tf.tile(options_taken_one_hot[..., None], [1, 1, self.action_size])
    pi_o = tf.reduce_sum(tf.multiply(self.options, options_taken_one_hot),
                         reduction_indices=1, name="pi_o")
    return pi_o

  def get_responsible_actions(self, policies, actions):
    actions_onehot = tf.one_hot(tf.cast(actions, tf.int32), self.action_size, dtype=tf.float32,
                                name="actions_one_hot")
    responsible_actions = tf.reduce_sum(policies * actions_onehot, [1])
    return responsible_actions

  def get_eigen_q(self, o):
    options_taken_one_hot = tf.one_hot(o, self.config.nb_options,
                                       name="options_one_hot")
    eigen_q_values_o = tf.reduce_sum(tf.multiply(self.eigen_q_val, options_taken_one_hot),
                                     reduction_indices=1, name="eigen_values_Q")
    return eigen_q_values_o

  def get_q(self, o):
    options_taken_one_hot = tf.one_hot(o, (
      self.config.nb_options + self.action_size) if self.config.include_primitive_options else self.config.nb_options,
                                       name="options_one_hot")
    q_values_o = tf.reduce_sum(tf.multiply(self.q_val, options_taken_one_hot),
                               reduction_indices=1, name="values_Q")
    return q_values_o

  def get_primitive(self, o):
    primitive_actions = tf.where(o >= self.nb_options,
                                 tf.ones_like(self.current_option),
                                 tf.zeros_like(self.current_option))
    return primitive_actions

  def get_o_term(self, o, boolean_value=False):
    options_taken_one_hot = tf.one_hot(o, self.config.nb_options,
                                       name="options_one_hot")
    o_term = tf.reduce_sum(tf.multiply(self.termination, options_taken_one_hot),
                           reduction_indices=1, name="o_terminations")
    if boolean_value:
      local_random = tf.random_uniform(shape=[], minval=0., maxval=1., dtype=tf.float32, name="rand_o_term")
      o_term = o_term > local_random
    return o_term

  def layer_norm_fn(x, relu=True):
    x = layers.layer_norm(x, scale=True, center=True)
    if relu:
      x = tf.nn.relu(x)
    return x
