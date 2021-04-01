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

AWAY_MAP = {'on': 'away',
            'away': 'away',
            'off': 'home',
            'home': 'home',
            True: 'away',
            False: 'home'}

FAN_MAP = {'auto on': False,
           'on': True,
           'auto': False,
           '1': True,
           '0': False,
           1: True,
           0: False,
           True: True,
           False: False}

LowHighTuple = collections.namedtuple('LowHighTuple', ('low', 'high'))

STRUCTURES = 'structures'
THERMOSTAT_TYPE = 'sdm.devices.types.THERMOSTAT'
SMOKE_CO_ALARMS = 'smoke_co_alarms'
CAMERAS = 'cameras'

# https://developers.nest.com/documentation/api-reference/overview#targettemperaturef
MINIMUM_TEMPERATURE_F = 50
MAXIMUM_TEMPERATURE_F = 90
# https://developers.nest.com/documentation/api-reference/overview#targettemperaturec
MINIMUM_TEMPERATURE_C = 9
MAXIMUM_TEMPERATURE_C = 32

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

class NestBase(object):
    def __init__(self, name, nest_api):
        self._name = name
        self._nest_api = nest_api

    def __str__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._repr_name)

    def _set(self, data):
        path = f'/{self.name}:executeCommand'

        response = self._nest_api._put(path=path, data=data)

        return response

    @property
    def name(self):
        return self._name

    @property
    def _repr_name(self):
        return self.name


class Device(NestBase):
    @property
    def _device(self):
        raise NotImplementedError("Implemented by subclass")

    @property
    def _devices(self):
        return self._nest_api._devices

    @property
    def _repr_name(self):
        if self.name:
            return self.name

        return self.where

    def __repr__(self):
        return str(self._device)

    @property
    def is_thermostat(self):
        return False

    @property
    def is_camera(self):
        return False

    @property
    def is_smoke_co_alarm(self):
        return False

    @property
    def where(self):
        return self._device['parentRelations']['displayName']


class Thermostat(Device):
    @property
    def is_thermostat(self):
        return True

    @property
    def _device(self):
        return next(device for device in self._devices if device['name'] == self.name)

    @property
    def humidity(self):
        return self._device['traits']['sdm.devices.traits.Humidity']['ambientHumidityPercent']

    @property
    def mode(self):
        return self._device['traits']['sdm.devices.traits.ThermostatMode']['mode']

    @property
    def temperature_scale(self):
        return self._device['traits']['sdm.devices.traits.Settings']['temperatureScale']

    @property
    def temperature(self):
        return self._device['traits']['sdm.devices.traits.Temperature']['ambientTemperatureCelsius']

    @property
    def hvac_state(self):
        return self._device['traits']['sdm.devices.traits.ThermostatHvac']['status']

    @property
    def heat_setpoint(self):
        return self._device['traits']['sdm.devices.traits.ThermostatTemperatureSetpoint']['heatCelsius']

    @heat_setpoint.setter
    def heat_setpoint(self, value):
        self._set({
                    "command" : "sdm.devices.commands.ThermostatMode.SetHeat",
                    "params" : {
                        "heatCelsius" : value
                    }
                })

class Camera(Device):
    @property
    def is_camera(self):
        return True

    @property
    def _device(self):
        return self._devices.get(CAMERAS, {}).get(self._serial, {})

    @property
    def ongoing_event(self):
        if self.last_event is not None and self.last_event.is_ongoing:
            return self.last_event

    def has_ongoing_motion_in_zone(self, zone_id):
        if self.ongoing_event is not None:
            return self.last_event.has_ongoing_motion_in_zone(zone_id)
        return False

    @property
    def sound_detected(self):
        if self.ongoing_event is not None:
            return self.last_event.has_ongoing_sound()
        return False

    @property
    def motion_detected(self):
        if self.ongoing_event is not None:
            return self.last_event.has_ongoing_motion()
        return False

    @property
    def person_detected(self):
        if self.ongoing_event is not None:
            return self.last_event.has_ongoing_person()
        return False

    @property
    def activity_zones(self):
        return [ActivityZone(self, z['id'])
                for z in self._device.get('activity_zones', [])]

    @property
    def last_event(self):
        if 'last_event' in self._device:
            return CameraEvent(self)

    @property
    def is_streaming(self):
        return self._device.get('is_streaming')

    @is_streaming.setter
    def is_streaming(self, value):
        self._set('devices/cameras', {'is_streaming': value})

    @property
    def is_video_history_enabled(self):
        return self._device.get('is_video_history_enabled')

    @property
    def is_audio_enabled(self):
        return self._device.get('is_audio_input_enabled')

    @property
    def is_public_share_enabled(self):
        return self._device.get('is_public_share_enabled')

    @property
    def model(self):
        return self._device.get('model')

    @property
    def snapshot_url(self):
        if ('snapshot_url' in self._device and
                self._device['snapshot_url'] != SIMULATOR_SNAPSHOT_URL):
            return self._device['snapshot_url']
        else:
            return SIMULATOR_SNAPSHOT_PLACEHOLDER_URL

    @property
    def web_url(self):
        return self._device.get('web_url')

class Nest(object):
    def __init__(self,
                 client_id=None, client_secret=None,
                 access_token=None, access_token_cache_file=None,
                 project_id=None,
                 reautherize_callback=None,
                 cache_period=1000):
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
        self._client = OAuth2Session(self._client_id, redirect_uri=REDIRECT_URI, scope=SCOPE)

        authorization_url, state = self._client.authorization_url(
            AUTHORIZE_URL.format(self.project_id),
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
                    token = self._client.refresh_token(ACCESS_TOKEN_URL, **extra)
                    self.__save_token(token)
                    if attempt > 1:
                        raise AuthorizationError(None, 'Repeated TokenExpiredError')
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

    @property
    def thermostats(self):
        names = [ device['name'] for device in 
            self._devices if device['type'] == THERMOSTAT_TYPE
        ]
        return [Thermostat(name, self) for name in names]

    @property
    def smoke_co_alarms(self):
        return [SmokeCoAlarm(devid, self)
                for devid in self._devices.get(SMOKE_CO_ALARMS, [])]

    @property
    def cameras(self):
        return [Camera(devid, self)
                for devid in self._devices.get(CAMERAS, [])]

    @property
    def structures(self):
        return [Structure(stid, self)
                for stid in self._status.get(STRUCTURES, [])]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False