# -*- coding: utf-8 -*-
# Copyright (c) Sebastian Klaassen. All Rights Reserved.
# Distributed under the MIT License. See LICENSE file for more info.

import os.path
import setuptools
import asyncframes

def read(filename):
    with open(os.path.join(os.path.dirname(__file__), filename)) as file:
        return file.read()

ld = read('README.rst') + '\n\n' + read('CHANGES.rst')

setuptools.setup(
    name='asyncframes',
    packages=['asyncframes'],
    version=asyncframes.__version__,
    description='Object oriented coroutines for everyone',
    long_description=read('README.rst') + '\n\n' + read('CHANGES.rst'),
    author='RcSepp',
    author_email='rcsepp@hotmail.com',
    license='MIT'
    #url='TODO'
)
