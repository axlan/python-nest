# -*- coding:utf-8 -*-
# a module of helper functions
# mostly for the configuration

import os
import configparser

from . import nest


class MissingCredentialsError(ValueError):
    pass


def get_config(config_path=None, prog='nest'):
    if not config_path:
        config_path = os.path.sep.join(('~', '.config', prog, 'config'))

    config_file = os.path.expanduser(config_path)

    defaults = {}

    # Note, this cannot accept sections titled 'DEFAULT'
    if os.path.exists(config_file):
        config = configparser.SafeConfigParser()
        config.read([config_file])
        if config.has_section('nest'):
            defaults.update(dict(config.items('nest')))
        elif config.has_section('NEST'):
            defaults.update(dict(config.items('NEST')))
        else:
            print('Incorrectly formatted configuration file.')
            exit()

    return defaults
