import numpy as np
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix

import keras.backend as K
from keras import optimizers
from keras.models import load_model
from keras.models import Sequential, Model
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.layers import Dense, Embedding, LSTM, GRU, Bidirectional, Input, Lambda
from keras.layers import Reshape, Conv2D, MaxPool2D, Concatenate, Flatten, Dropout


class keras_basemodel:

    MODEL_PATH = "keras_model"

    def train(self, train_x, train_y):


        ckpt_callback = ModelCheckpoint(self.MODEL_PATH, 
                                 monitor='val_loss', 
                                 verbose=1, 
                                 save_best_only=True, 
                                 mode='auto')
        es_callback = EarlyStopping(monitor='val_loss', 
                                  min_delta=0.01, 
                                  patience=10, 
                                  verbose=0, 
                                  mode='auto', 
                                  restore_best_weights=True)

        
        self.model.fit(train_x, train_y, 
                       epochs = self.config.epochs, 
                       batch_size = self.config.batch_size, 
                       validation_split = self.config.val_split,
                       callbacks = [ckpt_callback])


    def test(self, test_x, test_y):

        model = load_model(self.MODEL_PATH)
        probas = model.predict(test_x)
        y_pred = np.argmax(probas, axis=1)
        y_true = np.argmax(test_y, axis=1)
        
        result_string = classification_report(y_true, y_pred)
        print(confusion_matrix(y_true, y_pred))
        print(result_string)
        return classification_report(y_true, y_pred, output_dict=True), result_string





class text_GRU(keras_basemodel):

    def __init__(self, config):
        self.config = config

    def getModel(self, embeddingMatrix):

        
        input_utterance = Input(shape=(self.config.max_sent_length,), name="input")
        embeddingLayer = Embedding(input_dim=embeddingMatrix.shape[0], output_dim=embeddingMatrix.shape[1],
                                   weights=[embeddingMatrix],
                                   mask_zero=True, trainable=True)

        emb1 = embeddingLayer(input_utterance)
        rnn_out = Bidirectional(GRU(100, recurrent_dropout=0.5, dropout=0.5))(emb1)
        dense = Dense(64, activation='relu')(rnn_out)
        dense = Dense(32, activation='relu')(dense)
        dense2 = Dense(self.config.num_classes,activation='softmax')(dense)

        self.model = Model(inputs=[input_utterance], outputs=dense2)

        adam = optimizers.Adam(lr=0.0001)
        self.model.compile(loss = 'categorical_crossentropy', optimizer=adam,  metrics=['acc'])
        return self.model.summary()



class text_CNN(keras_basemodel):

    def __init__(self, config):
        self.config = config

    def getModel(self, embeddingMatrix):

        sentence_length = self.config.max_sent_length
        filter_sizes = self.config.filter_sizes
        embedding_dim = self.config.embedding_dim
        num_filters = self.config.num_filters


        input_utterance = Input(shape=(sentence_length,), name="input")
        embeddingLayer = Embedding(input_dim=embeddingMatrix.shape[0], output_dim=embeddingMatrix.shape[1],
                                   weights=[embeddingMatrix],
                                   trainable=False)

        emb1 = embeddingLayer(input_utterance)
        reshape = Reshape((sentence_length,self.config.embedding_dim,1))(emb1)
        conv_0 = Conv2D(num_filters, kernel_size=(filter_sizes[0], embedding_dim), padding='valid', 
                 kernel_initializer='normal', activation='relu', data_format="channels_last")(reshape)
        conv_1 = Conv2D(num_filters, kernel_size=(filter_sizes[1], embedding_dim), padding='valid', 
                 kernel_initializer='normal', activation='relu', data_format="channels_last")(reshape)
        conv_2 = Conv2D(num_filters, kernel_size=(filter_sizes[2], embedding_dim), padding='valid', 
                 kernel_initializer='normal', activation='relu', data_format="channels_last")(reshape)

        maxpool_0 = MaxPool2D(pool_size=(sentence_length - filter_sizes[0] + 1, 1), strides=(1,1), padding='valid')(conv_0)
        maxpool_1 = MaxPool2D(pool_size=(sentence_length - filter_sizes[1] + 1, 1), strides=(1,1), padding='valid')(conv_1)
        maxpool_2 = MaxPool2D(pool_size=(sentence_length - filter_sizes[2] + 1, 1), strides=(1,1), padding='valid')(conv_2)

        concatenated_tensor = Concatenate(axis=1)([maxpool_0, maxpool_1, maxpool_2])
        flatten = Flatten()(concatenated_tensor)

        dropout = Dropout(self.config.dropout_rate)(flatten)
        dense = Dense(128, activation='relu')(flatten)
        output_layer = Dense(self.config.num_classes,activation='softmax')(dense)

        self.model = Model(inputs=[input_utterance], outputs=output_layer)

        adam = optimizers.Adam(lr=0.0001)
        self.model.compile(loss = 'categorical_crossentropy', optimizer=adam,  metrics=['acc'])
        return self.model.summary()




class text_CNN_context(keras_basemodel):

    def __init__(self, config):
        self.config = config


    def getModel(self, embeddingMatrix):

        sentence_length = self.config.max_sent_length
        context_length = self.config.max_context_length
        filter_sizes = self.config.filter_sizes
        embedding_dim = self.config.embedding_dim
        num_filters = self.config.num_filters
        if self.config.use_author:
            num_authors = self.config.num_authors

        # Input layers
        input_utterance = Input(shape=(sentence_length,), name="input_utterance")

        if self.config.use_context:
            input_context = Input(shape=(context_length, sentence_length), name="input_context")
        
        if self.config.use_author:
            input_authors = Input(shape=(num_authors,), name="input_authors")
        
        # Layer functions
        embeddingLayer = Embedding(input_dim=embeddingMatrix.shape[0], output_dim=embeddingMatrix.shape[1],
                                   weights=[embeddingMatrix],
                                   trainable=False)

        def slicer(x, index):
            return x[:,K.constant(index, dtype='int32'),:]

        def slicer_output_shape(input_shape):
            shape = list(input_shape)
            assert len(shape) == 3  # batch, seq_len, sent_len
            new_shape = (shape[0], shape[2])
            return new_shape

        def reshaper(x, axis):
            return K.expand_dims(x, axis=axis)
        
        conv_0 = Conv2D(num_filters, kernel_size=(filter_sizes[0], embedding_dim), padding='valid', 
                 kernel_initializer='normal', activation='tanh', data_format="channels_last")
        conv_1 = Conv2D(num_filters, kernel_size=(filter_sizes[1], embedding_dim), padding='valid', 
                 kernel_initializer='normal', activation='tanh', data_format="channels_last")
        conv_2 = Conv2D(num_filters, kernel_size=(filter_sizes[2], embedding_dim), padding='valid', 
                 kernel_initializer='normal', activation='tanh', data_format="channels_last")
        maxpool_0 = MaxPool2D(pool_size=(sentence_length - filter_sizes[0] + 1, 1), strides=(1,1), padding='valid')
        maxpool_1 = MaxPool2D(pool_size=(sentence_length - filter_sizes[1] + 1, 1), strides=(1,1), padding='valid')
        maxpool_2 = MaxPool2D(pool_size=(sentence_length - filter_sizes[2] + 1, 1), strides=(1,1), padding='valid')
        dense_func = Dense(128, activation='relu', name="dense")

        # Network graph

        ## for target utterance
        utt_emb = embeddingLayer(input_utterance)

        def convolution_operation(input_sent):
            reshaped = Lambda(reshaper, arguments={'axis':3})(input_sent)
            concatenated_tensor = Concatenate(axis=1)([maxpool_0(conv_0(reshaped)), maxpool_1(conv_1(reshaped)), maxpool_2(conv_2(reshaped))])
            return Flatten()(concatenated_tensor)

        utt_conv_out = convolution_operation(utt_emb)

        ## for context utterances
        if self.config.use_context:
            cnn_output = []
            for ind in range(context_length):
                local_input = Lambda(slicer, output_shape=slicer_output_shape, arguments={"index":ind})(input_context) # Batch, word_indices
                local_utt_emb = embeddingLayer(local_input)
                local_utt_conv_out = convolution_operation(local_utt_emb)
                local_dense_output = dense_func(local_utt_conv_out)
                cnn_output.append(local_dense_output)
            
            def stack(x):
                return K.stack(x, axis=1)
            cnn_outputs = Lambda(stack)(cnn_output)

            def reduce_mean(x):
                return K.mean(x, axis=1)
        
            # context_vector = GRU(128)(cnn_outputs)
            context_vector= Lambda(reduce_mean)(cnn_outputs)
        
        if self.config.use_context:
            joint_input = Concatenate(axis=1)([utt_conv_out, context_vector])
        else:
            joint_input = utt_conv_out

        if self.config.use_author:
            joint_input = Concatenate(axis=1)([joint_input, input_authors])
        else:
            joint_input = Concatenate(axis=1)([joint_input])


        # dropout = Dropout(self.config.dropout_rate)(joint_input)
        dense = Dense(128, activation='relu')(joint_input)
        output_layer = Dense(self.config.num_classes,activation='softmax')(dense)

        # Define model input
        model_input = [input_utterance]
        if self.config.use_context:
            model_input.append(input_context)
        if self.config.use_author:
            model_input.append(input_authors)


        self.model = Model(inputs=model_input, outputs=output_layer)

        adam = optimizers.Adam(lr=0.0001)
        self.model.compile(loss = 'categorical_crossentropy', optimizer=adam,  metrics=['acc'])
        return self.model.summary()
    
