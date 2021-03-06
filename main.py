import tensorflow as tf
import numpy as np

import os
import sys
import atexit
import time
import logging

from DataProvider import DataProvider
from Configuration import Configuration as Config
from Utils import Utils

img_size = 64
inputN = img_size * img_size
classesN = 2

def logger():
	return logging.getLogger(Config.LOGGER_NAME)

def conv2d(x, w, b, strides=1):
	x = tf.nn.conv2d(x, w, strides=[1, strides, strides, 1], padding='SAME')
	x = tf.nn.bias_add(x, b)
	return tf.nn.relu(x)


def max_pool(conv):
	return tf.nn.max_pool(conv, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')


def conv_net(x, weights, biases, dropout):
	x = tf.reshape(x, shape=[-1, img_size, img_size, 3])

	conv1 = conv2d(x, weights['wc1'], biases['bc1'])

	conv2 = conv2d(conv1, weights['wc2'], biases['bc2'])

	conv3 = conv2d(conv2, weights['wc3'], biases['bc3'])
	conv3 = max_pool(conv3)

	fc1 = tf.reshape(conv3, [-1, weights['wd1'].get_shape().as_list()[0]])
	fc1 = tf.add(tf.matmul(fc1, weights['wd1']), biases['bd1'])
	fc1 = tf.nn.relu(fc1)

	fc1 = tf.nn.dropout(fc1, dropout)

	out = tf.add(tf.matmul(fc1, weights['out']), biases['out'])
	return out


def get_weights_and_biases():
	
	init_wc1 = np.sqrt(2.0/(3*img_size**2))
	init_wc2 = np.sqrt(2.0/(3*3*64)) 
	init_wc3 = np.sqrt(2.0/(3*3*64)) 

	init_wd1 = np.sqrt(2.0/(64*32*32))

	init_out = np.sqrt(2.0/512)

	weights = {

		# 7x7 conv, 3 input, 64 outputs
		'wc1': tf.Variable(init_wc1 * tf.random_normal([3, 3, 3, 64])),

		# 7x7 conv, 64 inputs, 64 outputs
		'wc2': tf.Variable(init_wc2 * tf.random_normal([3, 3, 64, 64])),

		# 5x5 conv, 64 inputs, 64 outputs
		'wc3': tf.Variable(init_wc3 * tf.random_normal([3, 3, 64, 64])),

		# fully connected, 8x8 - image size after 3 max_pooling (64/2/2/2/2)
		# x 32 - 32 outputs from previous layer
		'wd1': tf.Variable(init_wd1 * tf.random_normal([64*32*32, 512])),

		# 1024 inputs, 2 outputs (class prediction)
		'out': tf.Variable(init_out * tf.random_normal([512, classesN]))
	}

	biases = {
		'bc1': tf.Variable(0.1 * tf.random_normal([64])),
		'bc2': tf.Variable(0.1 * tf.random_normal([64])),
		'bc3': tf.Variable(0.1 * tf.random_normal([64])),
		'bd1': tf.Variable(0.1 * tf.random_normal([512])),
		'out': tf.Variable(0.1 * tf.random_normal([classesN]))
	}

	return weights, biases


def read_command_line():
	logger().info("Command line arguments:")
	logger().info(sys.argv)

	if (len(sys.argv) > 4):
		checkpoint_path = sys.argv[4]
		print "Changing CHECKPOINT_PATH to:" + checkpoint_path
		Config.CHECKPOINT_PATH = checkpoint_path 

	if (len(sys.argv) > 5):
		train_folder = sys.argv[5]
		print "Changing TRAIN_FOLDER to:" + train_folder
		Config.TRAIN_FOLDER = train_folder 	

	return int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])

def maybe_create_result_directory():
	Utils.maybe_create_directory(Config.CHECKPOINT_PATH)

def create_submission(session, model, keep_prob, x, data_provider):
	logger().info("Creating submission")

	submission_file = open("submission.csv", "w")

	progress = 0

	batch_size = 20
	batch_x, file_paths = data_provider.submission_data_batch(batch_size)

	while len(batch_x):
		pred_y = tf.argmax(tf.nn.softmax(model), 1)
		labels = pred_y.eval(feed_dict={x: batch_x, keep_prob: 1.}, session=session)
		save_labels(submission_file, labels, file_paths)

		progress = progress + len(batch_x)
		logger().info("analysed " + str(progress) + " images")

		batch_x, file_paths = data_provider.submission_data_batch(batch_size)

	submission_file.close()
	logger().info("Submission created")


def evaluate(sess, x, y, accuracy, keep_prob, data_provider):
	logger().info("evaluating")

	data_provider.load_verification_data_info()

	ckpt = tf.train.get_checkpoint_state(Config.CHECKPOINT_PATH)

	if ckpt and ckpt.model_checkpoint_path:
		saver = tf.train.Saver(tf.global_variables())
		saver.restore(sess, ckpt.model_checkpoint_path)
	else:
		logger().error("no model to be restored")
		return 0.0

	sumAcc = 0.0
	testSize = 0;

	batch_x, batch_y = data_provider.test_data_batch()

	while(len(batch_x)):

		acc = sess.run(accuracy, feed_dict={x: batch_x, y: batch_y, keep_prob: 1.})

		# logger().info("testing accuracy:" + str(acc) + " batchSize:" + str(len(batch_x)))

		sumAcc += acc * len(batch_x);
		testSize += len(batch_x);

		batch_x, batch_y = data_provider.test_data_batch()

	return sumAcc/testSize


def train(sess, x, y, optimizer, cost, accuracy, keep_prob, data_provider):
	logger().info("Start training")

	saver = tf.train.Saver(tf.global_variables())

	training_start = time.time()

	step = 1

	training_iters = Config.epochs * data_provider.train_images_count

	logger().info("Number of images to train:" + str(data_provider.train_images_count))
	logger().info(str(training_iters) + " needed to achieve " + str(Config.epochs) + " epochs")

	while step * Config.batch_size < training_iters:

		batch_x, batch_y = data_provider.next_data_batch()

		sess.run(optimizer, feed_dict={x: batch_x, y: batch_y, keep_prob: Config.dropout})

		if step % Config.display_step == 0:
			loss, acc = sess.run([cost, accuracy], feed_dict={x: batch_x, y: batch_y, keep_prob: 1.})
			msg = "Iter " + str(step * Config.batch_size) + ", Minibatch Loss= " + \
				  "{:.6f}".format(loss) + ", Training Accuracy= " + \
				  "{:.5f}".format(acc)

			logger().info(msg)

		if step % 20 == 0:
			logger().info("Saving model")
			saver.save(sess, os.path.join(Config.CHECKPOINT_PATH, 'model.ckpt'))

			## to be removed
			acc = evaluate(sess, x, y, accuracy, keep_prob, data_provider)
			logger().info("Iteration:" +str(step * Config.batch_size) + " Overall testing Accuracy:" + str(acc))
			## to be removed


		step += 1

	training_end = time.time()

	logger().info("Training finished. Time of training:" + str(training_end - training_start) + " s")

	saver.save(sess, os.path.join(Config.CHECKPOINT_PATH, 'model.ckpt'))		



def save_labels(submission_file, labels, file_paths):
	for label, file_path in zip(labels, file_paths):
		image_number = (((file_path.split('/'))[-1]).split('.'))[0]
		submission_file.write(str(image_number) + "," + str(label) + "\n")

def print_help():
	print "Too few arguments"
	print "main.py <should_train> <should_evaluate> <should_create_kaggle_submission>"
	print "For example: main.py 1 0 0"

def check_arguments_and_maybe_exit():
	if (len(sys.argv) < 4) :
			print_help()
			sys.exit()

def main():

	train_flag, eval_flag, submission_flag = read_command_line()

	Config.configure_logger()
	Config.save_config()

	check_arguments_and_maybe_exit()

	maybe_create_result_directory()

	weights, biases = get_weights_and_biases()

	x = tf.placeholder(tf.float32, [None, inputN, 3])
	y = tf.placeholder(tf.float32, [None, classesN])

	keep_prob = tf.placeholder(tf.float32)

	model = conv_net(x, weights, biases, keep_prob)

	cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(model, y))

	optimizer = tf.train.AdamOptimizer(learning_rate=Config.learning_rate).minimize(cost)

	correct_pred = tf.equal(tf.argmax(model, 1), tf.argmax(y, 1))
	accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

	init = tf.global_variables_initializer()

	data_provider = DataProvider(Config.TRAIN_FOLDER, Config.SUBMISSION_FOLDER, Config.VERIFICATION_FOLDER)

	with tf.Session() as sess:
		sess.run(init)
		saver = tf.train.Saver(tf.global_variables())

		if train_flag:
			train(sess, x, y, optimizer, cost, accuracy, keep_prob, data_provider)

		if eval_flag:
			acc = evaluate(sess, x, y, accuracy, keep_prob, data_provider)
			logger().info("Overall testing Accuracy:" + str(acc))

		if submission_flag:
			create_submission(sess, model, keep_prob, x, data_provider)


if __name__ == "__main__":
	main()
