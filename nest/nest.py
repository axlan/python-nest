# -*- coding:utf-8 -*-

import collections
import copy
import datetime
import hashlib
import logging
import threading
import time
import os
import uuid
import weakref

from dateutil.parser import parse as parse_time

import requests
from requests import auth
from requests import adapters
from requests.compat import json

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError

ACCESS_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
AUTHORIZE_URL = 'https://nestservices.google.com/partnerconnections/{project_id}/auth'
API_URL = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/{project_id}/devices'
REDIRECT_URI = 'https://www.google.com'
SCOPE = ['https://www.googleapis.com/auth/sdm.service']

_LOGGER = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, response, msg=None):
        if response is None:
            response_content = b''
        else:
            try:
                response_content = response.content
            except AttributeError:
                response_content = response.data

        if response_content != b'':
            if isinstance(response, requests.Response):
                try:
                    message = response.json()['error']
                except:
                    message = response_content
        else:
            message = "API Error Occured"

        if msg is not None:
            message = "API Error Occured: " + msg

        # Call the base class constructor with the parameters it needs
        super(APIError, self).__init__(message)

        self.response = response


class AuthorizationError(Exception):
    def __init__(self, response, msg=None):
        if response is None:
            response_content = b''
        else:
            try:
                response_content = response.content
            except AttributeError:
                response_content = response.data

        if response_content != b'':
            if isinstance(response, requests.Response):
                message = response.json().get(
                    'error_description',
                    "Authorization Failed")
        else:
            message = "Authorization failed"

        if msg is not None:
            message = "Authorization Failed: " + msg

        # Call the base class constructor with the parameters it needs
        super(AuthorizationError, self).__init__(message)

        self.response = response


class Device():

    def __init__(self, nest_api=None, name=None, device_data=None):
        self._name = name
        self._nest_api = nest_api
        self._device_data = device_data

    def __str__(self):
        trait_str = ','.join([f'<{k}: {v}>' for k, v in self.traits.items()])
        return f'name: {self.name} where:{self.where} - {self.type}({trait_str})'

    @property
    def name(self):
        if self._device_data is not None:
            return self._device_data['name']
        else:
            return self._name.split('/')[-1]

    @property
    def _device(self):
        if self._device_data is not None:
            return self._device_data
        else:
            return next(device for device in self._devices if self.name in device['name'])

    @property
    def _devices(self):
        if self._device_data is not None:
            raise RuntimeError("Invalid use of singular device")
        return self._nest_api._devices

    @property
    def where(self):
        return self._device['parentRelations'][0]['displayName']

    @property
    def type(self):
        return self._device['type'].split('.')[-1]

    @property
    def traits(self):
        return {k.split('.')[-1]: v for k, v in self._device['traits'].items()}

    @property
    def traits(self):
        return {k.split('.')[-1]: v for k, v in self._device['traits'].items()}

    def send_cmd(self, cmd, params):
        cmd = '.'.join(cmd.split('.')[-2:])
        path = f'/{self.name}:executeCommand'
        data = {
            "command": "sdm.devices.commands." + cmd,
            'params': params
        }
        response = self._nest_api._put(path=path, data=data)
        return response

    @staticmethod
    def filter_for_trait(devices, trait):
        trait = trait.split('.')[-1]
        return [device for device in devices if trait in device.traits]

    @staticmethod
    def filter_for_cmd(devices, cmd):
        trait = cmd.split('.')[-2]
        return Device.filter_for_trait(devices, trait)


class Nest(object):
    def __init__(self,
                 client_id=None, client_secret=None,
                 access_token=None, access_token_cache_file=None,
                 project_id=None,
                 reautherize_callback=None,
                 cache_period=10):
        self._client_id = client_id
        self._client_secret = client_secret
        self._project_id = project_id
        self._cache_period = cache_period
        self._access_token_cache_file = access_token_cache_file
        self._reautherize_callback = reautherize_callback
        self._last_update = 0
        self._client = None
        self._devices_value = {}

        if not access_token:
            try:
                with open(self._access_token_cache_file, 'r') as fd:
                    access_token = json.load(fd)
                    _LOGGER.debug("Loaded access token from %s",
                                  self._access_token_cache_file)
            except:
                _LOGGER.warn("Token load failed from %s",
                             self._access_token_cache_file)
        if access_token:
            self._client = OAuth2Session(self._client_id, token=access_token)

    def __save_token(self, token):
        with open(self._access_token_cache_file, 'w') as fd:
            json.dump(token, fd)
            _LOGGER.debug("Save access token to %s",
                          self._access_token_cache_file)

    def __reauthorize(self):
        if self._reautherize_callback is None:
            raise AuthorizationError(None, 'No callback to handle OAuth URL')
        self._client = OAuth2Session(
            self._client_id, redirect_uri=REDIRECT_URI, scope=SCOPE)

        authorization_url, state = self._client.authorization_url(
            AUTHORIZE_URL.format(project_id=self._project_id),
            # access_type and prompt are Google specific extra
            # parameters.
            access_type="offline", prompt="consent")
        authorization_response = self._reautherize_callback(authorization_url)
        _LOGGER.debug(">> fetch_token")
        token = self._client.fetch_token(
            ACCESS_TOKEN_URL,
            authorization_response=authorization_response,
            # Google specific extra parameter used for client
            # authentication
            client_secret=self._client_secret)
        self.__save_token(token)

    def _request(self, verb, path, data=None):
        url = self.api_url + path
        if data is not None:
            data = json.dumps(data)
        attempt = 0
        while True:
            attempt += 1
            if self._client:
                try:
                    _LOGGER.debug(">> %s %s", verb, url)
                    r = self._client.request(verb, url,
                                             allow_redirects=False,
                                             data=data)
                    _LOGGER.debug(f"<< {r.status_code}")
                    if r.status_code == 200:
                        return r.json()
                    if r.status_code != 401:
                        raise APIError(r)
                except TokenExpiredError as e:
                    # most providers will ask you for extra credentials to be passed along
                    # when refreshing tokens, usually for authentication purposes.
                    extra = {
                        'client_id': self._client_id,
                        'client_secret': self._client_secret,
                    }
                    _LOGGER.debug(">> refreshing token")
                    token = self._client.refresh_token(
                        ACCESS_TOKEN_URL, **extra)
                    self.__save_token(token)
                    if attempt > 1:
                        raise AuthorizationError(
                            None, 'Repeated TokenExpiredError')
                    continue
            self.__reauthorize()

    def _put(self, path, data=None):
        pieces = path.split('/')
        path = '/' + pieces[-1]
        return self._request('POST', path, data=data)

    @property
    def api_url(self):
        return API_URL.format(project_id=self._project_id)

    @property
    def _devices(self):
        if time.time() > self._last_update + self._cache_period:
            try:
                self._devices_value = self._request('GET', '')['devices']
                self._last_update = time.time()
            except Exception as error:
                # other error still set update_event to trigger retry
                _LOGGER.debug("Exception occurred in processing stream:"
                              " %s", error)
        return self._devices_value

    def get_devices(self, names=None, wheres=None, types=None):
        ret = []
        for device in self._devices:
            obj = Device(device_data=device)
            name_match = (names is None or obj.name in names)
            where_match = (wheres is None or obj.where in wheres)
            type_match = (types is None or obj.type in types)
            if name_match and where_match and type_match:
                ret.append(Device(nest_api=self, name=obj.name))
        return ret

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False
