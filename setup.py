#!/usr/bin/env python
# -*- coding:utf-8 -*-

import io

from setuptools import setup


# NOTE(jkoelker) Subjective guidelines for Major.Minor.Micro ;)
#                Bumping Major means an API contract change.
#                Bumping Minor means API bugfix or new functionality.
#                Bumping Micro means CLI change of any kind unless it is
#                    significant enough to warrant a minor/major bump.
version = '5.0.0'


setup(name='python-google-nest',
      version=version,
      description='Python API and command line tool for talking to the '
                  'Nest™ Thermostat through new Google API',
      long_description_content_type="text/markdown",
      long_description=io.open('README.md', encoding='UTF-8').read(),
      keywords='nest thermostat',
      author='Jonathan Diamond',
      author_email='feros32@gmail.com',
      url='https://github.com/axlan/python-nest/',
      packages=['nest'],
      install_requires=['requests_oauthlib'],
      entry_points={
          'console_scripts': ['nest=nest.command_line:main'],
      }
      )
