# Python API and command line tool for the Nest™ Thermostat

TODO: Fix build check
.. image:: https://travis-ci.org/jkoelker/python-nest.svg?branch=master
    :target: https://travis-ci.org/jkoelker/python-nest

**NOTE: This library support the new (post 2020) API provided by Google which replaced the original Nest Developers API.**

## Installation

```bash
    [sudo] pip install python-google-nest
```

## Google Device Access Registration

This is a fairly onerous process, so make sure to read the details before you begin.

The biggest roadblock is that access to this API requires registering with Google for Device Access <https://developers.google.com/nest/device-access/registration>. This has a one time $5 fee.

The documentation <https://developers.google.com/nest/device-access/get-started> walks you through the rest of the process.

At a high level it involves:

1. Making sure your Nest devices are linked to your Google account
2. Set up GCP (Google Cloud Platform) account <https://console.cloud.google.com/>
3. Set up a new GCP project
    1. Create a Oauth landing page and add your email as a test user
    2. Enable the Smart device management API
    3. Create an Oauth credential with the settings called from web server and https://www.google.com as the authorized redirect URI. Note the client ID and secret from this step.
4. In https://console.nest.google.com/device-access create a new project and add oauth client ID from step 3.3
5. Follow the series of queries in https://developers.google.com/nest/device-access/authorize to authorize devices

You should end up with the following pieces of information:
* project-id - ID of the project you created in https://console.nest.google.com/device-access
* oauth_client_id - value from setting up OAuth in https://console.cloud.google.com/ project
* client_secret - value from setting up OAuth in https://console.cloud.google.com/ project
* authorization_code - You get this value when you authorize your https://console.nest.google.com/device-access project to access your devices
* access-token - Token used to make requests to https://smartdevicemanagement.googleapis.com
* refresh-token - Used to get a new access-token when the old one expires

Be careful as you follow along the guide in <https://developers.google.com/nest/device-access/get-started>, since you're dealing with so many similar accounts and keys it can be easy to mix something up and you won't get particularly useful errors.

## Usage



If you use python-nest as a command line tool:
    You don't need to change, but there is a new command line option ``--keep-alive`` you can give a try.

If you use python-nest in a poll loop, to query Nest device's property in certain period, there are several noticeable changes:
    - The internal cache removed, the ``Structure`` and ``Device`` objects will always return their current state presented in Nest API. 
    - A persistence HTTP connection will keep open for each ``Nest`` object. Therefore, please avoid to create more than one Nest object in your program.
    - Your poll query would not hit the API rate limit, you can increase your poll frequency.

If you want to change to Push mode:
    You need to listen ``Nest.update_event``. 
    Please note, any data change in all of your structures an devices will set the ``update_event``. You don't know which field got update.

.. code-block:: python

    import nest

    napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file)
    while napi.update_event.wait():
        napi.update_event.clear()
        # assume you have one Nest Camera
        print (napi.structures[0].cameras[0].motion_detected)

If you use asyncio:
    You have to wrap ``update_event.wait()`` in an ``ThreadPoolExecutor``, for example:

.. code-block:: python

    import asyncio
    import nest

    napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file)
    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(nest_update(event_loop, napi))
    finally:
        event_loop.close()

    async def nest_update(loop, napi):
        with ThreadPoolExecutor(max_workers=1) as executor:
            while True:
                await loop.run_in_executor(executor, nest.update_event.wait)
                nest.update_event.clear()
                # assume you have one Nest Camera
                print (napi.structures[0].cameras[0].motion_detected)


Module
------

You can import the module as ``nest``.

.. code-block:: python

    import nest
    import sys

    client_id = 'XXXXXXXXXXXXXXX'
    client_secret = 'XXXXXXXXXXXXXXX'
    access_token_cache_file = 'nest.json'

    napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file)

    if napi.authorization_required:
        print('Go to ' + napi.authorize_url + ' to authorize, then enter PIN below')
        if sys.version_info[0] < 3:
            pin = raw_input("PIN: ")
        else:
            pin = input("PIN: ")
        napi.request_token(pin)

    for structure in napi.structures:
        print ('Structure %s' % structure.name)
        print ('    Away: %s' % structure.away)
        print ('    Security State: %s' % structure.security_state)
        print ('    Devices:')
        for device in structure.thermostats:
            print ('        Device: %s' % device.name)
            print ('            Temp: %0.1f' % device.temperature)

    # Access advanced structure properties:
    for structure in napi.structures:
        print ('Structure   : %s' % structure.name)
        print (' Postal Code                    : %s' % structure.postal_code)
        print (' Country                        : %s' % structure.country_code)
        print (' num_thermostats                : %s' % structure.num_thermostats)

    # Access advanced device properties:
        for device in structure.thermostats:
            print ('        Device: %s' % device.name)
            print ('        Where: %s' % device.where)
            print ('            Mode       : %s' % device.mode)
            print ('            HVAC State : %s' % device.hvac_state)
            print ('            Fan        : %s' % device.fan)
            print ('            Fan Timer  : %i' % device.fan_timer)
            print ('            Temp       : %0.1fC' % device.temperature)
            print ('            Humidity   : %0.1f%%' % device.humidity)
            print ('            Target     : %0.1fC' % device.target)
            print ('            Eco High   : %0.1fC' % device.eco_temperature.high)
            print ('            Eco Low    : %0.1fC' % device.eco_temperature.low)
            print ('            hvac_emer_heat_state  : %s' % device.is_using_emergency_heat)
            print ('            online                : %s' % device.online)

    # The Nest object can also be used as a context manager
    # It is only for demo purpose, please do not create more than one Nest object in your program especially after 4.0 release
    with nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file) as napi:
        for device in napi.thermostats:
            device.temperature = 23

    # Nest products can be updated to include other permissions. Before you
    # can access them with the API, a user has to authorize again. To handle this
    # and detect when re-authorization is required, pass in a product_version
    client_id = 'XXXXXXXXXXXXXXX'
    client_secret = 'XXXXXXXXXXXXXXX'
    access_token_cache_file = 'nest.json'
    product_version = 1337

    # It is only for demo purpose, please do not create more than one Nest object in your program especially after 4.0 release
    napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file, product_version=product_version)

    print("Never Authorized: %s" % napi.never_authorized)
    print("Invalid Token: %s" % napi.invalid_access_token)
    print("Client Version out of date: %s" % napi.client_version_out_of_date)
    if napi.authorization_required is None:
        print('Go to ' + napi.authorize_url + ' to authorize, then enter PIN below')
        pin = input("PIN: ")
        napi.request_token(pin)


    # NOTE: By default all datetime objects are timezone unaware (UTC)
    #       By passing ``local_time=True`` to the ``Nest`` object datetime objects
    #       will be converted to the timezone reported by nest. If the ``pytz``
    #       module is installed those timezone objects are used, else one is
    #       synthesized from the nest data
    napi = nest.Nest(username, password, local_time=True)
    print napi.structures[0].weather.current.datetime.tzinfo




In the API, all temperature values are reported and set in the temperature scale
the device is set to (as determined by the ``device.temperature_scale`` property).

Helper functions for conversion are in the ``utils`` module:

.. code-block:: python

    from nest import utils as nest_utils
    temp = 23.5
    fahrenheit = nest_utils.c_to_f(temp)
    temp == nest_utils.f_to_c(fahrenheit)


The utils function use ``decimal.Decimal`` to ensure precision.


Command line
------------

.. code-block:: bash

    usage: nest [-h] [--conf FILE] [--token-cache TOKEN_CACHE_FILE] [-t TOKEN]
                [--client-id ID] [--client-secret SECRET] [-k] [-c] [-s SERIAL]
                [-S STRUCTURE] [-i INDEX] [-v]
                {temp,fan,mode,away,target,humid,target_hum,show,camera-show,camera-streaming,protect-show}
                ...

    Command line interface to Nest™ Thermostats

    positional arguments:
      {temp,fan,mode,away,target,humid,target_hum,show,camera-show,camera-streaming,protect-show}
                            command help
        temp                show/set temperature
        fan                 set fan "on" or "auto"
        mode                show/set current mode
        away                show/set current away status
        target              show current temp target
        humid               show current humidity
        target_hum          show/set target humidty
        show                show everything
        camera-show         show everything (for cameras)
        camera-streaming    show/set camera streaming
        protect-show        show everything (for Nest Protect)

    optional arguments:
      -h, --help            show this help message and exit
      --conf FILE           config file (default ~/.config/nest/config)
      --token-cache TOKEN_CACHE_FILE
                            auth access token cache file
      -t TOKEN, --token TOKEN
                            auth access token
      --client-id ID        product id on developer.nest.com
      --client-secret SECRET
                            product secret for nest.com
      -k, --keep-alive      keep showing update received from stream API in show
                            and camera-show commands
      -c, --celsius         use celsius instead of farenheit
      -s SERIAL, --serial SERIAL
                            optional, specify serial number of nest thermostat to
                            talk to
      -S STRUCTURE, --structure STRUCTURE
                            optional, specify structure name toscope device
                            actions
      -i INDEX, --index INDEX
                            optional, specify index number of nest to talk to
      -v, --verbose         showing verbose logging

    examples:
        # If your nest is not in range mode
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET temp 73
        # If your nest is in range mode
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET temp 66 73

        nest --conf myconfig --client-id CLIENTID --client-secret SECRET fan --auto
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET target_hum 35

        # nestcam examples
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET camera-show
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET camera-streaming --enable-camera-streaming

        # Stream API example
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET --keep-alive show
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET --keep-alive camera-show

        # Set ETA 5 minutes from now
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET away --away --eta 5

A configuration file must be specified and used for the credentials to communicate with the NEST Thermostat initially.  Once completed and a token is generated, if you're using the default location for the token, the command line option will read from it automatically.


.. code-block:: ini

    [NEST]
    client_id = your_client_id
    client_secret = your_client_secret
    token_cache = ~/.config/nest/token_cache


The ``[NEST]`` section may also be named ``[nest]`` for convenience. Do not use ``[DEFAULT]`` as it cannot be read


History
=======
This module was originally a fork of `python-nest <https://github.com/jkoelker/python-nest>`_
which was a fork of `nest_thermostat <https://github.com/FiloSottile/nest_thermostat>`_
which was a fork of `pynest <https://github.com/smbaker/pynest>`_
