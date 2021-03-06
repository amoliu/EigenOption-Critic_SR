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
import numpy as np
import configs
from env_wrappers import _create_environment

def get_direction(matrix_folder):
  matrix = np.load(os.path.join(os.path.join(matrix_folder, "models"), "sf_transition_matrix.npy"))
  u, s, v = np.linalg.svd(matrix)
  # reduce_noise = s > 1
  # s = s[reduce_noise][::-1]
  # v = v[reduce_noise][::-1]

  return s[FLAGS.option], v[FLAGS.option] if not FLAGS.flip_eigen else -v[FLAGS.option]

def train(config, env_processes, logdir):
  tf.reset_default_graph()
  sess = tf.Session()
  previous_stage_logdir = os.path.join(logdir, "sf_repres")
  matrix_stage_logdir = os.path.join(logdir, "sf_matrix")
  stage_logdir = os.path.join(logdir, "plot_sf_policy")
  tf.gfile.MakeDirs(stage_logdir)
  with sess:
    with tf.device("/cpu:0"):
      with config.unlocked:
        config.logdir = logdir
        config.stage_logdir = stage_logdir
        config.matrix_stage_logdir = matrix_stage_logdir
        eval, evect = get_direction(config.matrix_stage_logdir)
        config.network_optimizer = getattr(tf.train, config.network_optimizer)
        global_step = tf.Variable(0, dtype=tf.int32, name='global_step', trainable=False)
        env = _create_environment(config)
        action_size = env.action_space.n
        global_network = config.network("global", config, action_size, 5)
        global_network.option = FLAGS.option
        agent = config.option_agent(env, 0, global_step, config, FLAGS.option, eval, evect, FLAGS.flip_eigen, 5)

      saver = utility.define_saver(exclude=(r'.*_temporary/.*',))
      loader = utility.define_saver(exclude=(r'.*_temporary/.*',))
      sess.run(tf.global_variables_initializer())
      ckpt = tf.train.get_checkpoint_state(os.path.join(previous_stage_logdir, "models"))
      print("Loading Model from {}".format(ckpt.model_checkpoint_path))
      loader.restore(sess, ckpt.model_checkpoint_path)
      sess.run(tf.local_variables_initializer())

      coord = tf.train.Coordinator()

      agent_threads = []
      thread = threading.Thread(target=(lambda: agent.plot_heatmap(sess, coord, saver)))
      thread.start()
      agent_threads.append(thread)

      coord.join(agent_threads)

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
  tf.app.flags.DEFINE_integer(
    'option', 3,
    'option to learn')
  tf.app.flags.DEFINE_boolean(
    'flip_eigen', True,
    'flip the direction of the eigenvector')
  tf.app.flags.DEFINE_string(
    # 'load_from', None,
    'load_from', "./logdir/6-ac",
    'Load directory to load models from.')
  tf.app.run()
