from Utils import Utils
import tensorflow as tf
import skimage.io
import numpy
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img
from Configuration import Configuration as Config
import matplotlib.pyplot as plt
import scipy.misc

class DataProvider:
    def __init__(self, train_folder, submission_folder, verification_folder):

        self.verification_images_count = 0
        self.train_images_count = 0

        self._train_folder = train_folder
        self._submission_folder = submission_folder
        self._verification_folder = verification_folder

        self._submission_file_paths = list()

        self._train_image_files = list()
        self._train_labels = list()

        self._test_image_files = list()
        self._test_labels = list()

        self.load_train_data_info()
        self.load_submission_data_info()

    def extract_image_file_names_with_labels(self, folder):
        files = Utils.files_in_path(folder)

        image_files = []
        image_labels = []

        for imageFilePath in files:
            label_name = imageFilePath[0:3]

            label = [0, 0]

            if label_name == "cat":
                label[0] = 1
            elif label_name == "dog":
                label[1] = 1

            image_files.append(folder + "/" + imageFilePath)
            image_labels.append(label)

        return image_files, image_labels

    def test_data_batch(self):
        test_image_files = self._test_image_files[0:Config.batch_size]
        test_labels = self._test_labels[0:Config.batch_size]

        self._test_image_files = self._test_image_files[Config.batch_size:]
        self._test_labels = self._test_labels[Config.batch_size:]

        images = list()

        for file_path in test_image_files:
            image = self.load_test_image(file_path)
            images.append(image)

        return numpy.array(images), numpy.array(test_labels)


    def next_data_batch(self):
        if len(self._train_image_files) < Config.batch_size:
            self.load_train_data_info()

        train_image_files = self._train_image_files[0:Config.batch_size]
        train_labels = self._train_labels[0:Config.batch_size]

        self._train_image_files = self._train_image_files[Config.batch_size:]
        self._train_labels = self._train_labels[Config.batch_size:]

        images = list()

        for file_path in train_image_files:
            image = self.load_train_image(file_path)
            images.append(image)

        return numpy.array(images), numpy.array(train_labels)


    def load_verification_data_info(self):
        self._test_image_files, self._test_labels = self.extract_image_file_names_with_labels(self._verification_folder)
        self.verification_images_count = len(self._test_image_files)
                
    def load_train_data_info(self):
        self._train_image_files, self._train_labels = self.extract_image_file_names_with_labels(self._train_folder)
        self._test_image_files, self._test_labels = self.extract_image_file_names_with_labels(self._verification_folder)

        self.verification_images_count = len(self._test_image_files)
        self.train_images_count = len(self._train_image_files)

    def load_submission_data_info(self):
        for i in range(1, 125001):
            file_path = self._submission_folder + "/" + str(i) + ".jpg"
            self._submission_file_paths.append(file_path)

    def submission_data_batch(self, batch_size):
        sliced_list = self._submission_file_paths[:batch_size]
        self._submission_file_paths = self._submission_file_paths[batch_size:]

        images = list()

        for file_path in sliced_list:
            image = self.load_image(file_path)
            images.append(image)

        return numpy.array(images), sliced_list

    @staticmethod
    def flatten(matrix):
        return [item for vector in matrix for item in vector]

    @staticmethod
    def add_noise(image):
    	
        datagen = ImageDataGenerator(
            rotation_range=40,
            width_shift_range=0.2,
            height_shift_range=0.2,
            rescale=1./255,
            shear_range=0.2,
            zoom_range=0.2,
            horizontal_flip=True,
            fill_mode='nearest'
        )

        x = image.reshape((1,) + image.shape)

        for batch in datagen.flow(x, batch_size=1):
            return batch[0]

    @staticmethod        
    def scale(image):
        datagen = ImageDataGenerator(
            rescale=1./255
        )

        x = image.reshape((1,) + image.shape)

        for batch in datagen.flow(x, batch_size=1):
            return batch[0]

    @staticmethod
    def load_train_image(image_file):
        image = skimage.io.imread(image_file).astype(numpy.float32)
        image = DataProvider.add_noise(image)
        image = DataProvider.flatten(image)
        return image

    @staticmethod
    def load_test_image(image_file):
        image = skimage.io.imread(image_file).astype(numpy.float32)
        image = DataProvider.scale(image)
        image = DataProvider.flatten(image)
        return image    


