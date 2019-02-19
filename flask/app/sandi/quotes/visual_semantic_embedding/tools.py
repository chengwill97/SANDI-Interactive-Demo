"""
A selection of functions for encoding images and sentences
"""
import theano
import theano.tensor as tensor
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams

import cPickle as pkl
import numpy

from collections import OrderedDict, defaultdict
from scipy.linalg import norm

from app import app

from app.sandi.quotes.visual_semantic_embedding.utils import load_params
from app.sandi.quotes.visual_semantic_embedding.utils import init_tparams

from app.sandi.quotes.visual_semantic_embedding.model import init_params
from app.sandi.quotes.visual_semantic_embedding.model import build_sentence_encoder
from app.sandi.quotes.visual_semantic_embedding.model import build_image_encoder

def load_model(dictionary_path, model_options, model_path):
    """
    Load all model components
    """

    worddict = dict()
    options = dict()

    app.logger.info('Loading dictionary {}'.format(dictionary_path))

    with open(dictionary_path, 'rb') as f:
        worddict = pkl.load(f)

    app.logger.info('Creating inverted dictionary...')

    word_idict = {v: k for k, v in worddict.iteritems()}
    word_idict[0] = '<eos>'
    word_idict[1] = 'UNK'

    app.logger.info('Loading model options {}'.format(model_options))

    with open(model_options, 'rb') as f:
        options = pkl.load(f)

    app.logger.info('Loading model parameters')

    params = init_params(options)
    params = load_params(model_path, params)
    tparams = init_tparams(params)

    app.logger.info('Compiling sentence encoder')

    trng = RandomStreams(1234)
    trng, [x, x_mask], sentences = build_sentence_encoder(tparams, options)
    f_senc = theano.function([x, x_mask], sentences, name='f_senc')

    app.logger.info('Compiling image encoder')
    trng, [im], images = build_image_encoder(tparams, options)
    f_ienc = theano.function([im], images, name='f_ienc')

    # Store everything we need in a dictionary
    app.logger.info('Packing up {}'.format(model_path))

    model = dict()
    model['options'] = options
    model['worddict'] = worddict
    model['word_idict'] = word_idict
    model['f_senc'] = f_senc
    model['f_ienc'] = f_ienc

    return model

def encode_sentences(model, X, verbose=False, batch_size=128):
    """
    Encode sentences into the joint embedding space
    """
    features = numpy.zeros((len(X), model['options']['dim']), dtype='float32')

    # length dictionary
    ds = defaultdict(list)
    captions = [s.split() for s in X]
    for i,s in enumerate(captions):
        ds[len(s)].append(i)

    # quick check if a word is in the dictionary
    d = defaultdict(lambda : 0)
    for w in model['worddict'].keys():
        d[w] = 1

    # Get features. This encodes by length, in order to avoid wasting computation
    for k in ds.keys():
        if verbose:
            app.logger.debug(k)
        numbatches = len(ds[k]) / batch_size + 1
        for minibatch in range(numbatches):
            caps = ds[k][minibatch::numbatches]
            caption = [captions[c] for c in caps]

            seqs = []
            for i, cc in enumerate(caption):
                seqs.append([model['worddict'][w] if d[w] > 0 and model['worddict'][w] < model['options']['n_words'] else 1 for w in cc])
            x = numpy.zeros((k+1, len(caption))).astype('int64')
            x_mask = numpy.zeros((k+1, len(caption))).astype('float32')
            for idx, s in enumerate(seqs):
                x[:k,idx] = s
                x_mask[:k+1,idx] = 1.

            ff = model['f_senc'](x, x_mask)
            for ind, c in enumerate(caps):
                features[c] = ff[ind]

    return features

def encode_images(model, IM):
    """
    Encode images into the joint embedding space
    """
    images = model['f_ienc'](IM)
    return images


