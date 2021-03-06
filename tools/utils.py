from math import floor

import numpy as np
import tensorflow as tf
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from scipy.signal import lfilter
import scipy.misc

# Copies one set of variables to another.
def update_target_graph(from_scope, to_scope):
  from_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, from_scope)
  to_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, to_scope)

  op_holder = []
  for from_var, to_var in zip(from_vars, to_vars):
    op_holder.append(to_var.assign(from_var))
  return op_holder


def update_target_graph_aux(from_scope, to_scope):
  from_vars = [v for v in tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, from_scope) if
               "sf" not in v.name and "option" not in v.name]
  to_vars = [v for v in tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, to_scope) if
             "sf" not in v.name and "option" not in v.name]

  op_holder = []
  for from_var, to_var in zip(from_vars, to_vars):
    op_holder.append(to_var.assign(from_var))
  return op_holder


def update_target_graph_sf(from_scope, to_scope):
  from_vars = [v for v in tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, from_scope) if "sf" in v.name]
  to_vars = [v for v in tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, to_scope) if "sf" in v.name]

  op_holder = []
  for from_var, to_var in zip(from_vars, to_vars):
    op_holder.append(to_var.assign(from_var))
  return op_holder


def update_target_graph_option(from_scope, to_scope):
  from_vars = [v for v in tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, from_scope) if "option" in v.name]
  to_vars = [v for v in tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, to_scope) if "option" in v.name]

  op_holder = []
  for from_var, to_var in zip(from_vars, to_vars):
    op_holder.append(to_var.assign(from_var))
  return op_holder


def discount(x, gamma):
  # axis = len(x.shape) - 1
  return np.flip(lfilter([1], [1, -gamma], np.flip(x, 0), axis=0), axis=0)

def reward_discount(x, gamma):
  return lfilter([1], [1, -gamma], x[::-1], axis=0)[::-1]


def normalized_columns_initializer(std=1.0):
  def _initializer(shape, dtype=None, partition_info=None):
    out = np.random.randn(*shape).astype(np.float32)
    out *= std / np.sqrt(np.square(out).sum(axis=0, keepdims=True))
    return tf.constant(out)

  return _initializer


def make_gif(images, fname, duration=2, true_image=False):
  import moviepy.editor as mpy

  def make_frame(t):
    try:
      x = images[int(len(images) / duration * t)]
    except:
      x = images[-1]

    if true_image:
      return x.astype(np.uint8)
    else:
      return ((x + 1) / 2 * 255).astype(np.uint8)

  clip = mpy.VideoClip(make_frame, duration=duration)
  clip.write_gif(fname, fps=len(images) / duration, verbose=False)

def set_image(s, option, action, episode_length, primitive):
  s_big = scipy.misc.imresize(255*(s/2 + 0.5), [200, 200, 3], interp='nearest')
  frame = Image.fromarray(np.asarray(s_big, np.uint8))
  draw = ImageDraw.Draw(frame)
  font = ImageFont.truetype("./resources/FreeSans.ttf", 10)
  draw.text((0, 0), "O: {} >> A: {} >> Len: {} >> Primitive >> {}".format(option, action, episode_length, primitive), (0, 0, 0), font=font)
  return np.asarray(frame)

def set_image_bandit(values, probs, selection, trial):
  bandit_image = Image.open('./resources/bandit.png')
  draw = ImageDraw.Draw(bandit_image)
  font = ImageFont.truetype("./resources/FreeSans.ttf", 24)
  draw.text((40, 10), str(float("{0:.2f}".format(probs[0]))), (0, 0, 0), font=font)
  draw.text((130, 10), str(float("{0:.2f}".format(probs[1]))), (0, 0, 0), font=font)
  draw.text((60, 370), 'Trial: ' + str(trial), (0, 0, 0), font=font)
  bandit_image = np.array(bandit_image)
  bandit_image[115:115 + floor(values[0] * 2.5), 20:75, :] = [0, 255.0, 0]
  bandit_image[115:115 + floor(values[1] * 2.5), 120:175, :] = [0, 255.0, 0]
  bandit_image[101:107, 10 + (selection * 95):10 + (selection * 95) + 80, :] = [80.0, 80.0, 225.0]
  return bandit_image


def set_image_bandit_11_arms(values, target_arm, selection, trial):
  bandit_image = Image.open('./resources/11arm.png')
  draw = ImageDraw.Draw(bandit_image)
  font = ImageFont.truetype("./resources/FreeSans.ttf", 24)
  print("target arm is {}. Selection is {}".format(target_arm, selection))
  delta = 90
  draw.text((40 + 1 * delta, 10), "T", (0, 0, 0), font=font)
  draw.text((40 + 2 * delta, 10), "I {}".format(target_arm), (0, 0, 0), font=font)
  draw.text((40 + 0 * delta, 10), "S", (0, 0, 0), font=font)
  draw.text((60, 370), 'Trial: ' + str(trial), (0, 0, 0), font=font)
  bandit_image = np.array(bandit_image)
  delta = 100
  for i in range(11):
    if i == target_arm:
      bandit_image[115:115 + floor(values[i] / 5 * 2.5), (20 + delta * 1):(75 + delta * 1), :] = [0, 255.0, 0]
    elif i == 10:
      bandit_image[115:115 + floor(values[i] / 5 * 2.5), (20 + delta * 2):(75 + delta * 2), :] = [0, 255.0, 0]
    else:
      bandit_image[115:115 + floor(values[i] / 5 * 2.5), (20 + delta * 0):(75 + delta * 0), :] = [0, 255.0, 0]
  if selection == target_arm:
    bandit_image[101:107, 10 + delta * 1:10 + delta * 1 + 85, :] = [80.0, 80.0, 225.0]
  elif selection == 10:
    bandit_image[101:107, 10 + delta * 2:10 + delta * 2 + 85, :] = [80.0, 80.0, 225.0]
  else:
    bandit_image[101:107, 10 + delta * 0:10 + delta * 0 + 85, :] = [80.0, 80.0, 225.0]
  return bandit_image
