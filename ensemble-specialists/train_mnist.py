from __future__ import division

import os
import sys

import numpy as np
import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data
import tensorflow.contrib.slim as slim

import model

u_str = sys.argv[1]
u = [int(i) for i in u_str]

######################
# Data Configuration #
######################
chkpt_dir = 'checkpoints-%s/' % u_str
data_dir = 'mnist_data'

##############################
# Target Model Configuration #
##############################
REG_WEIGHT = 1e-6
LR_START   = 9e-4
LR_END     = 7e-5

N_EPOCHS = 30
BATCH_SIZE = 128

INPUT_DIM = 28
INPUT_CHANNELS = 1
N_CLASSES = 10

if not os.path.exists(chkpt_dir):
    os.makedirs(chkpt_dir)

####################
# Tensorflow Model #
####################

# Placeholders
X  = tf.placeholder(shape=(None, INPUT_DIM, INPUT_DIM, INPUT_CHANNELS),
                    dtype=tf.float32, name='X')
y  = tf.placeholder(shape=(None, N_CLASSES), dtype=tf.float32, name='y')
lr = tf.placeholder(tf.float32)
tr_mode = tf.placeholder(tf.bool)

# Model
logits, softmax = model.model(X, N_CLASSES, tr_mode, REG_WEIGHT)

# Loss function
cross_entropy  = slim.losses.softmax_cross_entropy(logits=logits, onehot_labels=y)
regularization = tf.add_n(slim.losses.get_regularization_losses())

# loss = cross_entropy # Disable regularization (following CleverHans model)
loss = cross_entropy + regularization

# Evaluation metrics
correct_pred = tf.equal(tf.argmax(logits, 1), tf.argmax(y, 1))
accuracy     = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

# Optimize
train_step = tf.train.AdamOptimizer(lr).minimize(loss)

# Fire up the Tensorflow session!
init = tf.global_variables_initializer()
gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.95)
sess = tf.Session(config=tf.ConfigProto(
    intra_op_parallelism_threads=8,
    gpu_options=gpu_options))
sess.run(init)
saver = tf.train.Saver()

# Load in data
data = input_data.read_data_sets(data_dir, one_hot=True)
def filter_dataset(ds):
    selected = np.in1d(np.argmax(ds._labels, 1), u)
    ds._images = ds._images[selected]
    ds._labels = ds._labels[selected]
    ds._num_examples = ds._images.shape[0]
    print 'selecting', ds._num_examples, 'of', selected.shape[0] # %%%
for ds in data.train, data.validation, data.test:
    filter_dataset(ds)
# import code; code.interact(local=dict(globals(), **locals())); exit(1) # %%%

print(" ") # Skip a line

# Compute training parameters
n_train = data.train.num_examples
n_iters = int(np.ceil((1.0 * N_EPOCHS * n_train) / BATCH_SIZE))
epoch = lambda i: int((i * BATCH_SIZE) / n_train) + 1

anneal_rate = (-1.0 * np.log(LR_END / LR_START)) / float(n_iters)

# Set up validation set
x_val = np.reshape(data.validation.images, [-1, INPUT_DIM, INPUT_DIM, INPUT_CHANNELS])
eval_dict = { X: x_val, y: data.validation.labels, tr_mode: False }

# Set up test set
x_test = np.reshape(data.test.images, [-1, INPUT_DIM, INPUT_DIM, INPUT_CHANNELS])
test_dict = { X: x_test, y: data.test.labels, tr_mode: False }

#################
# Training loop #
#################
best_loss, curr_lr, curr_epoch = 1.0e20, LR_START, 1
fstr = """Iter {:05d} (epoch {:03d}) - validation loss = {:.6f}
     Validation accuracy.... = {:.6f}
     Checkpointed........... = {}
"""

for i in range(n_iters):
    # Anneal learning rate
    if i % 25 == 0 and anneal_rate > 0.0:
        if sess.run(loss, feed_dict=eval_dict) < best_loss:
            curr_lr = LR_START * np.exp(-1.0 * anneal_rate * i)

    # Train step
    batch = data.train.next_batch(BATCH_SIZE)
    x = np.reshape(batch[0], [-1, INPUT_DIM, INPUT_DIM, INPUT_CHANNELS])
    sess.run(train_step, feed_dict={ X: x, y: batch[1], lr: curr_lr, tr_mode: True })

    # Log and checkpoint @ end of each epoch
    if curr_epoch != epoch(i + 1):
        val_loss, curr_epoch, checkpointed = sess.run(loss, feed_dict=eval_dict), epoch(i + 1), False
        if val_loss < best_loss:
            best_loss, checkpointed = val_loss, True
            saver.save(sess, chkpt_dir + 'mnist_weights.ckpt')
        print(fstr.format(i, epoch(i), val_loss, sess.run(accuracy, feed_dict=eval_dict), checkpointed))

# Finish training
print("Optimization finished!")
saver.save(sess, chkpt_dir + 'max_iters.ckpt') # Save final weights

# Test set evaluation
fstr_test = "Test set performance: loss = {:.6f}, accuracy = {:.6f}\n"
print(fstr_test.format(
    sess.run(loss,     feed_dict=test_dict),
    sess.run(accuracy, feed_dict=test_dict)))

# Restore -best- model
print("Restoring model with lowest validation loss...")
saver.restore(sess, chkpt_dir + 'mnist_weights.ckpt')
print(fstr_test.format(
    sess.run(loss,     feed_dict=test_dict),
    sess.run(accuracy, feed_dict=test_dict)))
