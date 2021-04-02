#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import io

from setuptools import setup


#                Bumping Major means an API contract change.
#                Bumping Minor means API bugfix or new functionality.
#                Bumping Micro means CLI change of any kind unless it is
#                    significant enough to warrant a minor/major bump.
version = '5.0.1'


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
      classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
      ],
      python_requires=">=3.6",
      packages=['nest'],
      install_requires=[
          # Tested with requests_oauthlib==1.3.0
          'requests_oauthlib'
        ],
      entry_points={
          'console_scripts': ['nest=nest.command_line:main'],
      }
      )
