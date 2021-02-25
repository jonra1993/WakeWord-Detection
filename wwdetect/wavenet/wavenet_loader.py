import h5py
import numpy as np
from tqdm import tqdm
import tensorflow as tf


class HeySnipsDataset(tf.keras.utils.Sequence):
    def __init__(self, data_file, batch_size=32, num_features=40, 
                 shuffle=False, *args, **kwargs):

        # dataset pre-fetch
        self.dataset, self.num_wakewords = self.preload_data(data_file)

        # state variables
        self.num_features = num_features
        self.batch_size = batch_size
        self.num_batches = len(self.dataset) // batch_size
        self.shuffle = shuffle

    def __len__(self):
        # returns the number of batches
        return self.num_batches 

    def __getitem__(self, index):
        # returns one batch

        # find which segments make up the batch
        batch_start = self.batch_size * index 
        batch_idxs = np.arange(batch_start, batch_start + self.batch_size)

        # load batch features and labels 
        X = [self.dataset[i]['features'] for i in batch_idxs]
        y = np.array([self.dataset[i]['label'] for i in batch_idxs])

        # make each batch uniform length
        X = self.pad_features(X)

        return X, y

    def prune_wakewords(self, keep_ratio):

        # find indexes of all wakewords in dataset
        wakeword_idxs = []
        for i in range(len(self.dataset)):
            if self.dataset[i]['label'] == 1:
                wakeword_idxs.append(i)

        # move wakewords to new datastruct
        # must be done in reversed order or idxs won't match up as they are removed
        wakewords = []
        for i in reversed(wakeword_idxs):
            # copy example to new list
            wakewords.append(self.dataset[i])

            # delete example from original dataset to not keep duplicates
            del self.dataset[i]

        # shuffle so removal is not order dependent
        np.random.shuffle(wakewords)

        # discard 1-keep_ratio of wakeword examples from datset
        self.dataset = self.dataset + wakewords[:int(keep_ratio*self.num_wakewords)]

        # reshuffle dataset so wakewords are not at the end
        np.random.shuffle(self.dataset)

        # set new number of batchs in dataset
        self.num_batches = len(self.dataset) // self.batch_size

    def get_labels(self):
        assert not self.shuffle, "Order may not be correct due to shuffling being enabled"
        return [self.dataset[i]['label'] for i in range(self.number_of_examples())]

    def get_filenames(self):
        assert not self.shuffle, "Order may not be correct due to shuffling being enabled"
        return [self.dataset[i]['file_name'] for i in range(self.number_of_examples())]

    def number_of_examples(self):
        # returns number of examples in dataset
        return len(self.dataset)
    
    def number_of_wakewords(self):
        # returns number of wakewords in test set (does not account for pruning)
        return self.num_wakewords

    def on_epoch_end(self):
        # option method to run some logic at the end of each epoch: e.g. reshuffling
        if self.shuffle:
            np.random.shuffle(self.dataset)

    def pad_features(self, X):

        # create new datastruct of max length timesteps 
        max_length = max([x.shape[0] for x in X])
        X_padded = np.zeros((len(X), max_length, X[0].shape[-1]), dtype=np.float32)

        # pad features
        for idx, features in enumerate(X):
            features = np.expand_dims(features, 0)
            X_padded[idx, :features.shape[1], :features.shape[2]] = features 
        return X_padded 

    def preload_data(self, data_file):

        self.dataset = []
        self.num_wakewords = 0
        print(f'pre-loading dataset from file {data_file}')
        with h5py.File(data_file, 'r') as h5:
            keys = list(h5.keys())
            for key in tqdm(keys):
                self.dataset.append({'file_name': key, 
                                     'label': np.uint8(h5[key].attrs['is_hotword']),
                                     'start_speech': np.int16(h5[key].attrs['speech_start_ts']),
                                     'end_speech': np.int16(h5[key].attrs['speech_end_ts']),
                                     'features': np.array(h5[key][()], dtype=np.float32)})

                # count number of wakewords in dataset
                if h5[key].attrs['is_hotword'] == 1:
                    self.num_wakewords += 1

        return self.dataset, self.num_wakewords

if __name__ == '__main__':
    # Test Loader
    data_file = 'data/test.h5'
    dataloader = HeySnipsDataset(data_file)
