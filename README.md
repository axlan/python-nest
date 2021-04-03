# Python API and command line tool for the Nest™ Thermostat

**NOTE: This library support the new (post 2020) API provided by Google which replaced the original Nest Developers API.**

For a write up on developing this library see: <https://www.robopenguins.com/nest/>

## Installation

This library does not support Python2

```bash
    [sudo] pip install python-google-nest
```

In addition to the Python library it also adds a CLI tool `nest` that is documented [below](#command-line)

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
5. Follow the series of queries in https://developers.google.com/nest/device-access/authorize to authorize devices. **Note** This step handled by this library.

Be careful as you follow along the guide in <https://developers.google.com/nest/device-access/get-started>, since you're dealing with so many similar accounts and keys it can be easy to mix something up and you won't get particularly useful errors.

You should end up with the following pieces of information:
* project_id - ID of the project you created in https://console.nest.google.com/device-access
* client_id - value from setting up OAuth in https://console.cloud.google.com/ project
* client_secret - value from setting up OAuth in https://console.cloud.google.com/ project

you will need those values to use this library.

## Authentication

This library uses those values to authenticate itself using refresh token grants. See <https://docs.wso2.com/display/IS530/Refresh+Token+Grant>

![Auth flow](https://docs.wso2.com/download/attachments/60493896/OAuth%20grant%20types%20-%20refresh-token.png?version=2&modificationDate=1510629793000&api=v2)

The first time you use this library you'll need to follow a URL the library generates to https://nestservices.google.com/partnerconnections and authenticate your devices with your Google account. When you finish this process your browser will have a URL that looks like `https://www.google.com/?state=SOME_STATE_VALUE&code=SOME_AUTHENTICATION_CODE&scope=https://www.googleapis.com/auth/sdm.service` that you need to copy and paste into the callback.

This will be cached and for however long the token is valid the library will keep refreshing the token cache. Eventually you'll be prompted to reauthenticate.

## Usage

At a high level this library is used to get references to the devices included in the account. These references can be sent commands, and have a list of "traits". See <https://developers.google.com/nest/device-access/traits> for details on these traits and commands.

See docstring comments in <https://github.com/axlan/python-nest/blob/master/nest/nest.py> for details on the usage of this library.

Example:

```python
# reautherize_callback should be set to a function with the signature
# Callable[[str], str]] it will be called if the user needs to reautherize
# the OAuth tokens. It will be passed the URL to go to, and need to have
# the resulting URL after authentication returned.

with nest.Nest(client_id, client_secret
               ,project_id,
               access_token_cache_file=access_token_cache_file,
               reautherize_callback=reautherize_callback,
               cache_period=cache_period) as napi:

    # Will trigger initial auth and fetch of data
    devices = napi.get_devices(args.name, args.structure)

    # For a list of traits and commands see:
    # https://developers.google.com/nest/device-access/traits

    if cmd == 'show_trait':
        # will reuse the cached result unless cache_period has elapsed
        devices = nest.Device.filter_for_trait(devices, args.trait_name)
        # will reuse the cached result unless cache_period has elapsed
        print(devices[args.index].traits[args.trait_name])
    elif cmd == 'cmd':
        # will reuse the cached result unless cache_period has elapsed
        devices = nest.Device.filter_for_cmd(devices, args.cmd_name)
        # will trigger a request to POST the cmd
        print(devices[args.index].send_cmd(
            args.cmd_name, json.loads(args.cmd_params)))
    elif cmd == 'show':
        try:
            while True:
                for device in devices:
                    # will reuse the cached result and trigger a new request
                    # each time the cache_period elapses
                    print(device)
                print('=========================================')
                if not args.keep_alive:
                    break
                time.sleep(2)
        except KeyboardInterrupt:
            return
```

### Command Line

```bash
usage: nest [-h] [--conf FILE] [--token-cache TOKEN_CACHE_FILE] [-t TOKEN] [--client-id ID] [--client-secret SECRET] [--project-id PROJECT] [-k] [-n NAME] [-S STRUCTURE] [-i INDEX] [-v] {show_trait,cmd,show} ...

Command line interface to Nest™ Thermostats

positional arguments:
  {show_trait,cmd,show}
                        command help
    show_trait          show a trait
    cmd                 send a cmd
    show                show everything

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
  --project-id PROJECT  device access project id
  -k, --keep-alive      keep showing update received from stream API in show and camera-show commands
  -n NAME, --name NAME  optional, specify name of nest thermostat to talk to
  -S STRUCTURE, --structure STRUCTURE
                        optional, specify structure name toscope device actions
  -i INDEX, --index INDEX
                        optional, specify index number of nest to talk to
  -v, --verbose         showing verbose logging
```

examples:

```bash
# Show all of your devices
$ nest --conf myconfig show
name: AVPHwEvCbK85AJxEDHLe91Uf73nesTCg9RyUKBq2r5G2bDnKd_6OoVek1n8JtM4WlGoqsJpCBQkl9ny4oPkTiLith-XSLQ where:Downstairs - THERMOSTAT(<Info: {'customName': ''}>,<Humidity: {'ambientHumidityPercent': 45}>,<Connectivity: {'status': 'ONLINE'}>,<Fan: {}>,<ThermostatMode: {'mode': 'HEAT', 'availableModes': ['HEAT', 'OFF']}>,<ThermostatEco: {'availableModes': ['OFF', 'MANUAL_ECO'], 'mode': 'OFF', 'heatCelsius': 4.4444427, 'coolCelsius': 24.444443}>,<ThermostatHvac: {'status': 'OFF'}>,<Settings: {'temperatureScale': 'CELSIUS'}>,<ThermostatTemperatureSetpoint: {'heatCelsius': 20.44426}>,<Temperature: {'ambientTemperatureCelsius': 22.75}>)
name: AVPHwEteWa8QXa8PQ7MMzh2CtnzgDPcQCfggZquzPyF__9wUCU7gp0EhO4-_17JiB4WlNupsP3dL28TJmA9-GknM6voZPw where:Upstairs - THERMOSTAT(<Info: {'customName': ''}>,<Humidity: {'ambientHumidityPercent': 44}>,<Connectivity: {'status': 'ONLINE'}>,<Fan: {}>,<ThermostatMode: {'mode': 'HEAT', 'availableModes': ['HEAT', 'OFF']}>,<ThermostatEco: {'availableModes': ['OFF', 'MANUAL_ECO'], 'mode': 'OFF', 'heatCelsius': 4.4444427, 'coolCelsius': 24.444443}>,<ThermostatHvac: {'status': 'OFF'}>,<Settings: {'temperatureScale': 'CELSIUS'}>,<ThermostatTemperatureSetpoint: {'heatCelsius': 20.44426}>,<Temperature: {'ambientTemperatureCelsius': 24.809998}>)
name: AVPHwEsz8-DzdIJjNkb7iY5A5HPla6UEy7azMVyXlerdgrcuabbuLMyvlGjMLWdmqtydqtXHWfx7GHmHMaVKSDysceL4XA where:Downstairs - DOORBELL(<Info: {'customName': ''}>,<CameraLiveStream: {'maxVideoResolution': {'width': 640, 'height': 480}, 'videoCodecs': ['H264'], 'audioCodecs': ['AAC']}>,<CameraImage: {'maxImageResolution': {'width': 1920, 'height': 1200}}>,<CameraPerson: {}>,<CameraSound: {}>,<CameraMotion: {}>,<CameraEventImage: {}>)
=========================================
# add the --keep-alive to update the results every 2 seconds until killed with keyboard interrupt

# Show all of your devices in the "Upstairs" structure
$ nest --conf myconfig -S Upstairs show
name: AVPHwEteWa8QXa8PQ7MMzh2CtnzgDPcQCfggZquzPyF__9wUCU7gp0EhO4-_17JiB4WlNupsP3dL28TJmA9-GknM6voZPw where:Upstairs - THERMOSTAT(<Info: {'customName': ''}>,<Humidity: {'ambientHumidityPercent': 44}>,<Connectivity: {'status': 'ONLINE'}>,<Fan: {}>,<ThermostatMode: {'mode': 'HEAT', 'availableModes': ['HEAT', 'OFF']}>,<ThermostatEco: {'availableModes': ['OFF', 'MANUAL_ECO'], 'mode': 'OFF', 'heatCelsius': 4.4444427, 'coolCelsius': 24.444443}>,<ThermostatHvac: {'status': 'OFF'}>,<Settings: {'temperatureScale': 'CELSIUS'}>,<ThermostatTemperatureSetpoint: {'heatCelsius': 20.44426}>,<Temperature: {'ambientTemperatureCelsius': 24.809998}>)
=========================================

# Show the device with the matching name
$ nest --conf myconfig -n AVPHwEsz8-DzdIJjNkb7iY5A5HPla6UEy7azMVyXlerdgrcuabbuLMyvlGjMLWdmqtydqtXHWfx7GHmHMaVKSDysceL4XA show
name: AVPHwEsz8-DzdIJjNkb7iY5A5HPla6UEy7azMVyXlerdgrcuabbuLMyvlGjMLWdmqtydqtXHWfx7GHmHMaVKSDysceL4XA where:Downstairs - DOORBELL(<Info: {'customName': ''}>,<CameraLiveStream: {'maxVideoResolution': {'width': 640, 'height': 480}, 'videoCodecs': ['H264'], 'audioCodecs': ['AAC']}>,<CameraImage: {'maxImageResolution': {'width': 1920, 'height': 1200}}>,<CameraPerson: {}>,<CameraSound: {}>,<CameraMotion: {}>,<CameraEventImage: {}>)
=========================================

# Show the CameraImage trait of a device
$ nest --conf myconfig show_trait CameraImage
{'maxImageResolution': {'width': 1920, 'height': 1200}}

# Set the ThermostatMode to "HEAT"
$ nest --conf myconfig cmd ThermostatMode.SetMode '{"mode":"HEAT"}'
{}
```

A configuration file may be specified and used for the credentials to communicate with the NEST Thermostat.

```ini

    [NEST]
    client_id = your_client_id
    client_secret = your_client_secret
    project_id = your_project_id
    token_cache = ~/.config/nest/token_cache
```

The `[NEST]` section may also be named `[nest]` for convenience. Do not use `[DEFAULT]` as it cannot be read

## Unimplemented Features

There are two main parts of this API that are not implemented.

1. This library does not handle the Device Access event Pub/Sub system <https://developers.google.com/nest/device-access/subscribe-to-events>. Using these would avoid needing to poll the API.
2. This library does not currently handle getting video/images from the cameras. This should be possible to implement on top of this library, but would require setting up a RTSP client, or the logic to follow the links in the camera events.
3. Google provides libraries to discover the details of an API and generate code <https://developers.google.com/nest/device-access/reference/rest>. I took a look at this process, and it didn't seem like it wouldn't make a good fit for a simple library like this.

History
=======
This module is a fork of [python-nest](https://github.com/jkoelker/python-nest)
which was a fork of [nest_thermostat](https://github.com/FiloSottile/nest_thermostat)
which was a fork of [pynest](https://github.com/smbaker/pynest)
