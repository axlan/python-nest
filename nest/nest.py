# -*- coding:utf-8 -*-

import logging
import time
import os
import threading
from typing import Dict, Any, List, Callable, Optional

import requests
from requests.compat import json

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError

# Interface URLs
ACCESS_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
AUTHORIZE_URL = 'https://nestservices.google.com/partnerconnections/{project_id}/auth'
API_URL = 'https://smartdevicemanagement.googleapis.com/v1/enterprises/{project_id}/devices'
REDIRECT_URI = 'https://www.google.com'
SCOPE = ['https://www.googleapis.com/auth/sdm.service']

_LOGGER = logging.getLogger(__name__)


class Device():
    """This is the class used to access the traits of a Nest device

    You can access a list of traits and send commands.
    The class is linked back to a Nest instance which will keep it updated
    based on the Nest objects cache_period.

    Since any access can trigger a network request, they can result in exceptions
    """

    def __init__(self, nest_api: Optional['Nest'] = None,
                 name: Optional[str] = None,
                 device_data: Optional[Dict[str, Any]] = None):
        """Meant for internal use, get instances of Device from the Nest api

        Devices returned have the nest_api and name set.

        Parameters
        ----------
        nest_api : Nest
            The Nest instance providing updates
        name : str
            The unique name of this device
        device_data : Dict
            Instead of specifying the previous two, intialize directly from the
            dict for the device returned from the API call. Used internally.
        """

        self._name = name
        self._nest_api = nest_api
        self._device_data = device_data

    def __str__(self):
        trait_str = ','.join([f'<{k}: {v}>' for k, v in self.traits.items()])
        return f'name: {self.name} where:{self.where} - {self.type}({trait_str})'

    @property
    def name(self) -> str:
        """str representing the unique name of the device"""
        if self._device_data is not None:
            full_name = self._device_data['name']
        else:
            full_name = self._name
        return full_name.split('/')[-1]

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
    def where(self) -> str:
        """str representing the parent structure of the device"""
        return self._device['parentRelations'][0]['displayName']

    @property
    def type(self) -> str:
        """str representing the type of device"""
        return self._device['type'].split('.')[-1]

    @property
    def traits(self) -> Dict[str, Any]:
        """list of traits see https://developers.google.com/nest/device-access/traits"""
        return {k.split('.')[-1]: v for k, v in self._device['traits'].items()}

    def send_cmd(self, cmd: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to this device

        commands are listed in https://developers.google.com/nest/device-access/traits

        Parameters
        ----------
        cmd : str
            The string for the command can include the full command ie:
            "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool"
            or just the last two parts ie:
            "ThermostatTemperatureSetpoint.SetCool"
        params : dict
            The content of the params to send with the command

        Exceptions
        ----------
        Will return APIError if the command or params is invalid

        Returns
        -------
        Dict
        The body of the response
        """
        cmd = '.'.join(cmd.split('.')[-2:])
        path = f'/{self.name}:executeCommand'
        data = {
            "command": "sdm.devices.commands." + cmd,
            'params': params
        }
        response = self._nest_api._put(path=path, data=data)
        return response

    @staticmethod
    def filter_for_trait(devices: List['Device'], trait: str) -> List['Device']:
        """Filter a list of Devices for ones with a the specified trait"""
        trait = trait.split('.')[-1]
        return [device for device in devices if trait in device.traits]

    @staticmethod
    def filter_for_cmd(devices: List['Device'], cmd: str) -> List['Device']:
        """Filter a list of Devices for ones with a trait associated with a cmd

        ie. "ThermostatTemperatureSetpoint.SetCool" will filter for devices
        with the "ThermostatTemperatureSetpoint" trait
        """
        trait = cmd.split('.')[-2]
        return Device.filter_for_trait(devices, trait)


class Nest(object):
    """This is the class used to manage the connection to Google Smart Devices

    It handles the authentication flow and returns a list of the devices
    associated with the account. These devices will call back to this class
    to keep their values up to date.
    """

    def __init__(self,
                 client_id: str, client_secret: str,
                 project_id: str,
                 access_token: Optional[Dict[str, Any]] = None,
                 access_token_cache_file: Optional[str] = None,
                 reautherize_callback: Optional[Callable[[str], str]] = None,
                 cache_period: float = 10):
        """
        Parameters
        ----------
        client_id : str
            OAuth client_id
        client_secret : str
            OAuth secret
        project_id : str
            The project_id from https://console.nest.google.com/device-access/project-list
        access_token : Optional[Dict[str, Any]]
            Directly specify the OAuth access token ie.:
            {"access_token": "", "expires_in": 3599,
            "scope": ["https://www.googleapis.com/auth/sdm.service"],
            "token_type": "Bearer", "expires_at": 1617334543.9341743,
            "refresh_token": ""}
        access_token_cache_file : Optional[str]
            A path to store and load tokens to avoid needing to reauthentic
            every time.
        reautherize_callback : Optional[Callable[[str], str]]
            If the token is expired or invalid, this callback will be called
            with the URL the user needs to go to to revalidate. If not set
            an AuthorizationError exception will trigger.
        cache_period : float
            When requesting the device set, how long should the previous
            results be reused before making a new request.
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._project_id = project_id
        self._cache_period = cache_period
        self._access_token_cache_file = access_token_cache_file
        self._reautherize_callback = reautherize_callback
        self._lock = threading.Lock()
        self._last_update = 0
        self._client = None
        self._devices_value = {}

        if not access_token and self._access_token_cache_file:
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
        if self._access_token_cache_file:
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
        url = self._api_url + path
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
    def _api_url(self):
        return API_URL.format(project_id=self._project_id)

    @property
    def _devices(self):
        if time.time() > self._last_update + self._cache_period:
            with self._lock:
                try:
                    self._devices_value = self._request('GET', '')['devices']
                    self._last_update = time.time()
                except Exception as error:
                    # other error still set update_event to trigger retry
                    _LOGGER.debug("Exception occurred in processing stream:"
                                  " %s", error)
        return self._devices_value

    def get_devices(self, names: Optional[List[str]] = None,
                    wheres: Optional[List[str]] = None,
                    types: Optional[List[str]] = None) -> List[Device]:
        """Return the list of devices on this account that match the specified criteria

        Parameters
        ----------
        names : Optional[List[str]]
            return devices that have names that appear in this list if not None
        wheres : Optional[List[str]]
            return devices that have where values that appear in this list if not None
        types : Optional[List[str]]
            return devices that have types that appear in this list if not None
        """
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
