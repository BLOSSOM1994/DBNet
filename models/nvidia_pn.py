import os
import sys

import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()

import scipy
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, '../utils'))

import tf_util
import pointnet


def placeholder_inputs(batch_size, img_rows=66, img_cols=200, points=16384, separately=False):
    imgs_pl = tf.placeholder(tf.float32, shape=(batch_size, img_rows, img_cols, 3))
    pts_pl = tf.placeholder(tf.float32, shape=(batch_size, points, 3))
    if separately:
        speeds_pl = tf.placeholder(tf.float32, shape=(batch_size))
        angles_pl = tf.placeholder(tf.float32, shape=(batch_size))
        labels_pl = [speeds_pl, angles_pl]
    labels_pl = tf.placeholder(tf.float32, shape=(batch_size, 2))
    return imgs_pl, pts_pl, labels_pl


def get_model(net, is_training, bn_decay=None, separately=False):
    """ NVIDIA regression model, input is BxWxHx3, output Bx2"""
    batch_size = net[0].get_shape()[0].value
    img_net, pt_net = net[0], net[1]

    for i, dim in enumerate([24, 36, 48, 64, 64]):
        scope = "conv" + str(i + 1)
        img_net = tf_util.conv2d(img_net, dim, [5, 5],
                                 padding='VALID', stride=[1, 1],
                                 bn=True, is_training=is_training,
                                 scope=scope, bn_decay=bn_decay)

    img_net = tf.reshape(img_net, [batch_size, -1])
    img_net = tf_util.fully_connected(img_net, 256, bn=True,
                                      is_training=is_training,
                                      scope='img_fc0',
                                      bn_decay=bn_decay)
    with tf.variable_scope('pointnet'):
        pt_net = pointnet.get_model(pt_net, tf.constant(True))
    net = tf.reshape(tf.stack([img_net, pt_net], axis=2), [batch_size, 512])

    for i, dim in enumerate([256, 128, 16]):
        fc_scope = "fc" + str(i + 1)
        dp_scope = "dp" + str(i + 1)
        net = tf_util.fully_connected(net, dim, bn=True,
                                      is_training=is_training,
                                      scope=fc_scope, 
                                      bn_decay=bn_decay)
        net = tf_util.dropout(net, keep_prob=0.7,
                              is_training=is_training,
                              scope=dp_scope)

    net = tf_util.fully_connected(net, 2, activation_fn=None, scope='fc5')

    return net


def get_loss(pred, label, l2_weight=0.0001):
    diff = tf.square(tf.subtract(pred, label))
    train_vars = tf.trainable_variables()
    l2_loss = tf.add_n([tf.nn.l2_loss(v) for v in train_vars[1:]]) * l2_weight
    loss = tf.reduce_mean(diff + l2_loss)
    tf.summary.scalar('l2 loss', l2_loss * l2_weight)
    tf.summary.scalar('loss', loss)

    return loss


def summary_scalar(pred, label):
    threholds = [5, 4, 3, 2, 1, 0.5]
    angles = [float(t) / 180 * scipy.pi for t in threholds]
    speeds = [float(t) / 20 for t in threholds]

    for i in range(len(threholds)):
        scalar_angle = "angle(" + str(angles[i]) + ")"
        scalar_speed = "speed(" + str(speeds[i]) + ")"
        ac_angle = tf.abs(tf.subtract(pred[:, 1], label[:, 1])) < threholds[i]
        ac_speed = tf.abs(tf.subtract(pred[:, 0], label[:, 0])) < threholds[i]
        ac_angle = tf.reduce_mean(tf.cast(ac_angle, tf.float32))
        ac_speed = tf.reduce_mean(tf.cast(ac_speed, tf.float32))

        tf.summary.scalar(scalar_angle, ac_angle)
        tf.summary.scalar(scalar_speed, ac_speed)


if __name__ == '__main__':
    with tf.Graph().as_default():
        inputs = [tf.zeros((32, 66, 200, 3)), tf.zeros((32, 16384, 3))]
        outputs = get_model(inputs, tf.constant(True))
        print(outputs)
