#!/usr/bin/env python3

import os
import shutil

if os.path.exists('test'):
    shutil.rmtree('test')
os.mkdir('test')

def process(path, depth):
    if depth > 0:
        for c in "abc":
            newdir = os.path.join(path, 'dir_' + c)
            os.mkdir(newdir)
            process(newdir, depth-1)
    for c in "abcd":
        newfile = os.path.join(path, 'file_' + c + '.txt')
        os.system('dd if=/dev/urandom of={} bs=1M count=1'.format(newfile))

process('test', 4)
