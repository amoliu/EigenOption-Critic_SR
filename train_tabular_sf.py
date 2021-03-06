import threading
import matplotlib
matplotlib.use('Agg')
import datetime
import os
import gym
import tensorflow as tf
import tools
import utility
from tools import wrappers
import configs
from env_wrappers import _create_environment
import numpy as np
import math

def train(config, env_processes, logdir):
  tf.reset_default_graph()
  sess = tf.Session()
  stage_logdir = os.path.join(logdir, "tabular_sf")
  tf.gfile.MakeDirs(stage_logdir)
  with sess:
    with tf.device("/cpu:0"):
      with config.unlocked:
        config.logdir = logdir
        config.stage_logdir = stage_logdir
        config.network_optimizer = getattr(tf.train, config.network_optimizer)
        env =_create_environment(config)
        action_size = env.action_space.n
        nb_states = env.nb_states
        sf = np.eye((env.nb_states))
        delta = np.inf
        theta = 1
        while (theta < delta):
          delta = 0.0
          for s in range(nb_states):
            sf_s = sf[s]
            a = np.random.choice(range(action_size))
            s1, r = env.get_next_state_and_reward(
              s, a)
            state_features = np.identity(nb_states)
            sf_s1 = state_features[s] + config.discount * sf[s1]
            delta = max(delta, np.sum(np.abs(sf_s - sf_s1)))
            sf[s] = sf_s1

        u, s, v = np.linalg.svd(sf)
        print(s)

def recreate_directory_structure(logdir):
  if not tf.gfile.Exists(logdir):
    tf.gfile.MakeDirs(logdir)
  if not FLAGS.resume and FLAGS.train:
    tf.gfile.DeleteRecursively(logdir)
    tf.gfile.MakeDirs(logdir)


def main(_):
  utility.set_up_logging()
  if not FLAGS.config:
    raise KeyError('You must specify a configuration.')
  if FLAGS.load_from:
    logdir = FLAGS.logdir = FLAGS.load_from
  else:
    if FLAGS.logdir and os.path.exists(FLAGS.logdir):
      run_number = [int(f.split("-")[0]) for f in os.listdir(FLAGS.logdir) if os.path.isdir(os.path.join(FLAGS.logdir, f)) and FLAGS.config in f]
      run_number = max(run_number) + 1 if len(run_number) > 0 else 0
    else:
      run_number = 0
    logdir = FLAGS.logdir and os.path.expanduser(os.path.join(
      FLAGS.logdir, '{}-{}'.format(run_number, FLAGS.config)))
  try:
    config = utility.load_config(logdir)
  except IOError:
    config = tools.AttrDict(getattr(configs, FLAGS.config)())
    config = utility.save_config(config, logdir)
  train(config, FLAGS.env_processes, logdir)


if __name__ == '__main__':
  FLAGS = tf.app.flags.FLAGS
  tf.app.flags.DEFINE_string(
    'logdir', None,
    'Base directory to store logs.')
  tf.app.flags.DEFINE_string(
    'timestamp', datetime.datetime.now().strftime('%Y%m%dT%H%M%S'),
    'Sub directory to store logs.')
  tf.app.flags.DEFINE_string(
    'config', None,
    'Configuration to execute.')
  tf.app.flags.DEFINE_boolean(
    'env_processes', True,
    'Step environments in separate processes to circumvent the GIL.')
  tf.app.flags.DEFINE_boolean(
    'train', True,
    'Training.')
  tf.app.flags.DEFINE_boolean(
    'resume', False,
    'Resume.')
  tf.app.flags.DEFINE_boolean(
    'show_training', False,
    'Show gym envs.')
  tf.app.flags.DEFINE_string(
    'task', "sf",
    'Task nature')
  tf.app.flags.DEFINE_string(
    'load_from', None,
    # 'load_from', "./logdir/6-ac",
    'Load directory to load models from.')
  tf.app.run()
