#!/usr/bin/env python
# coding: utf-8

import torch
import torch.nn as nn
from torch.autograd import Variable

import os
import argparse
from layer import QRNNLayer
from model import QRNNModel

from data_utils import fopen
from data_utils import load_inv_dict
from data_utils import seq2words

from data_iterator import TextIterator
from data_iterator import prepare_batch

use_cuda = torch.cuda.is_available()

def load_model(config):
    model_path = os.path.join(config.model_dir, config.model_name)
    if os.path.exists(model_path):
        print 'Reloading model parameters..'
        ckpt = torch.load(model_path)
        model = QRNNModel(QRNNLayer, 
                          ckpt['num_layers'], ckpt['kernel_size'], 
                          ckpt['hidden_size'], ckpt['emb_size'], 
    	                  ckpt['num_enc_symbols'], ckpt['num_dec_symbols'])

        model.load_state_dict(ckpt['state_dict'])

    else:
    	raise ValueError(
    		'No such file:[{}]'.format(config.model_path))
    return model


def decode(config):
    # Load source data to decode
    test_set = TextIterator(source=config.decode_input,
                            source_dict=config.src_vocab,
                            batch_size=config.batch_size,
                            n_words_source=config.num_enc_symbols,
                            maxlen=None)

    model = load_model(config)
    target_inv_dict = load_inv_dict(config.tgt_vocab)

    if use_cuda:
        model = model.cuda()

    try:
        fout = fopen(config.decode_output, 'w')
        for idx, source_seq in enumerate(test_set):
            source, source_len = prepare_batch(source_seq)

            if use_cuda:
                source = Variable(source.cuda())
                source_len = Variable(source_len.cuda())
            else:
                source = Variable(source)
                source_len = Variable(source_len)

            states, memories = model.encode(source, source_len)
            
            preds_prev = Variable(
                torch.zeros(config.batch_size, config.max_decode_step + model.kernel_size-1).long())
            preds_prev[:,model.kernel_size-1] = (torch.ones(config.batch_size, ) * data_utils.start_token).long()
            preds = torch.zeros(config.batch_size, config.max_decode_step).long()

            if use_cuda:
                preds_prev.cuda(); preds.cuda()

            for t in xrange(config.max_decode_step):
                # logits: [batch_size x 1, tgt_vocab_size]
                states, logits = model.decode(preds_prev[:,t:t+model.kernel_size], 
                                              states, memories, keep_len=False)
                outputs = torch.max(logits, dim=1)[1]
                preds[:,t] = outputs
                preds_prev[:,t+model.kernel_size] = outputs

            for seq in preds:
                fout.write(str(seq2words(seq, target_inv_dict)) + '\n')
                fout.flush()

            print '  {}th line decoded'.format(idx * config.batch_size)
        print 'Decoding terminated'

    except IOError:
        pass
    finally:
        fout.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Decoding parameters
    parser.add_argument('--model_path', type=str, default=None)
    parser.add_argument('--decode_input', type=str, default=None)
    parser.add_argument('--decode_output', type=str, default=None)
    parser.add_argument('--batch_size', type=int, default=1)
    parser.add_argument('--max_decode_step', type=int, default=100)
    
    config = parser.parse_args()
    print(config)
    decode(config)
    print('DONE')
