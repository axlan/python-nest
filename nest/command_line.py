#! /usr/bin/python3
# -*- coding:utf-8 -*-

'''
nest.py -- a python interface to the Nest Thermostats
'''

from __future__ import print_function

import argparse
import datetime
import logging
import os
import time
import sys
import errno
import json

from . import nest
from . import helpers


def get_parser():
    # Get Executable name
    prog = os.path.basename(sys.argv[0])

    config_file = os.path.sep.join(('~', '.config', 'nest', 'config'))
    token_cache = os.path.sep.join(('~', '.config', 'nest', 'token_cache'))

    conf_parser = argparse.ArgumentParser(prog=prog, add_help=False)

    conf_parser.add_argument('--conf', default=config_file,
                             help='config file (default %s)' % config_file,
                             metavar='FILE')

    args, _ = conf_parser.parse_known_args()

    defaults = helpers.get_config(config_path=args.conf)

    description = 'Command line interface to Nest™ Thermostats'
    parser = argparse.ArgumentParser(description=description,
                                     parents=[conf_parser])

    parser.add_argument('--token-cache', dest='token_cache',
                        default=token_cache,
                        help='auth access token cache file',
                        metavar='TOKEN_CACHE_FILE')

    parser.add_argument('-t', '--token', dest='token',
                        help='auth access token', metavar='TOKEN')

    parser.add_argument('--client-id', dest='client_id',
                        help='product id on developer.nest.com', metavar='ID')

    parser.add_argument('--client-secret', dest='client_secret',
                        help='product secret for nest.com', metavar='SECRET')

    parser.add_argument('--project-id', dest='project_id',
                        help='device access project id', metavar='PROJECT')

    parser.add_argument('-k', '--keep-alive', dest='keep_alive',
                        action='store_true',
                        help='keep showing update received from stream API '
                             'in show and camera-show commands')

    parser.add_argument('-n', '--name', dest='name',
                        help='optional, specify name of nest '
                             'thermostat to talk to')

    parser.add_argument('-S', '--structure', dest='structure',
                        help='optional, specify structure name to'
                             'scope device actions')

    parser.add_argument('-i', '--index', dest='index', default=0, type=int,
                        help='optional, specify index number of nest to '
                             'talk to')

    parser.add_argument('-v', '--verbose', dest='verbose',
                        action='store_true',
                        help='showing verbose logging')

    subparsers = parser.add_subparsers(dest='command',
                                       help='command help')
    show_trait = subparsers.add_parser('show_trait', help='show a trait')
    show_trait.add_argument('trait_name',
                            help='name of trait to show')

    cmd = subparsers.add_parser('cmd', help='send a cmd')
    cmd.add_argument('cmd_name',
                     help='name of cmd to send')
    cmd.add_argument('cmd_params',
                     help='json for cmd params')

    subparsers.add_parser('show', help='show everything')

    parser.set_defaults(**defaults)
    return parser


def reautherize_callback(authorization_url):
    print('Please go to %s and authorize access.' % authorization_url)
    return input('Enter the full callback URL: ')


def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.verbose:
        logger = logging.getLogger('nest')
        logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s (%(threadName)s) "
            "[%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

    # This is the command(s) passed to the command line utility
    cmd = args.command
    if cmd is None:
        parser.print_help()
        return

    def _identity(x):
        return x

    display_temp = _identity

    # Expand the path to check for existence
    config_dir = os.path.expanduser("~/.config/nest")

    # Check if .config directory exists
    if not os.path.exists(config_dir):

        # If it does not, create it
        try:
            os.makedirs(config_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    token_cache = os.path.expanduser(args.token_cache)

    if args.client_id is None or args.client_secret is None or args.project_id is None:
        print("Missing client_id, project_id or client_secret. If using a "
              "configuration file, ensure that it is formatted properly, with "
              "a section titled as per the documentation-otherwise, call with "
              "--client-id and --client-secret.")
        return

    with nest.Nest(project_id=args.project_id, client_id=args.client_id,
                   client_secret=args.client_secret,
                   access_token=args.token,
                   access_token_cache_file=token_cache,
                   reautherize_callback=reautherize_callback) as napi:

        devices = napi.get_devices(args.name, args.structure)

        if cmd == 'show_trait':
            devices = nest.Device.filter_for_trait(devices, args.trait_name)
            print(devices[args.index].traits[args.trait_name])
        elif cmd == 'cmd':
            devices = nest.Device.filter_for_cmd(devices, args.cmd_name)
            print(devices[args.index].send_cmd(
                args.cmd_name, json.loads(args.cmd_params)))
        elif cmd == 'show':
            try:
                while True:
                    for device in devices:
                        print(device)
                    print('=========================================')
                    if not args.keep_alive:
                        break
                    time.sleep(2)
            except KeyboardInterrupt:
                return


if __name__ == '__main__':
    main()
