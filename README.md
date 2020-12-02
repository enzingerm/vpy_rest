# REST API for Viessmann heating controls

* Python `asyncio` based
* Configuration with `YAML`

Structure of this README:
- [Setup and requirements](#setup)
- [Configuration](#configuration)
- [API documentation](#api)


## Setup
- A serial connection to an Viessmann Optolink device needs to be available to the system (e.g. `/dev/ttyUSB0`)
- The basic requirements have to be installed: `pip install -r requirements.txt`
- Configure the application
- Then start the application by running `python run.py`

## Configuration
By default, a file called `config.yaml` is expected in the program directory. The basic building blocks of the configuration file are unit configuration sections, encoding configuration sections and parameter configuration sections. These are described in detail below and then the structure of the complete configuration file is described afterwards.

### Unit configuration

A unit defines how to is defined by a configuration section looking as follows:
```yaml
type: <builtin_unit_type>
unit_param_1: <value>
unit_param_2: <value>
...
```
**Builtin unit types:**
- `control_program_day` Stores the switching times for one day
  - no parameters
- `array` Stores consecutive values of another unit
  - Parameters:
    - `length`: number of 'child' values
    - `child`: another unit configuration section
      - *Note*: currently only `control_program_day` is accepted as child unit type
- `operating_status` Stores the operating status of a specific device/actor
  - no parameters
- `number` General purpose unit for numeric values
  - Parameters:
    - `min`: minimal accepted value
    - `max`: maximal accepted value
    - `integer`: true if only integral values are accepted, false otherwise
    - `suffix`: a suffix being appended to values of this unit, e.g. *°C* for temperature
- `system_time` Stores a combination of date and time
- `hour` Stores an operation hour counter


### Encoding configuration
An encoding is defined by a configuration section looking as follows:
```yaml
type: <builtin_encoding_type>
encoding_param_1: <value>
encoding_param_2: <value>
...
```
**Builtin encoding types:**
- `float` Encodes a decimal number
  - Parameters:
    - `size`: size of a value using this encoding in bytes
    - `factor`: integral number by which the value is divided after retrieving from the heating control
- `int` Encodes an integral number
  - Parameters:
    - `size`: size in bytes
- `control_program_day` Encodes the switching times for one day
  - no parameters
- `array` Encodes multiple consecutive values of using a 'child' encoding
  - Parameters:
    - `length`: number of child values
    - `child`: another encoding configuration section

### Parameter configuration
A parameter is configured by a configuration section looking as follows:
```yaml
id: <parameter_id> # this is the name by which the parameter is accessed using the REST API
name: <Human readable parameter name>
unit: <unit_coniguration> # see below how to configure the unit of a value
readonly: true if the parameter shouldn't be writable 
```

### Complete configuration
The complete configuration file might look like this (default values are given, if possible):

*config.yaml*
```yaml
---
config:
  server:
    ip: 127.0.0.1
    port: 8000
  api:
    auth:
      provider: token # may be set to none to not require authentication
      token_validity_days: 90 # how long a token should be valid before requiring reauthentication
      backend:
        type: list # may also be set to 'kerberos' or 'dummy' (accepts everything)
        users:
          - username: john
            password: secret
          - username: robert
            password: very_secret
          ...
    prometheus_metrics:
      enabled: false # whether the /metrics endpoint should be accessible (never requires authentication)
      mappings: # list of parameter - prometheus metric mappings
        - param: <param_section>
          prometheus_name: <prometheus metric name>
          type: <prometheus_metric_type> # gauge, counter, ...
        ...
    highlevel:
      hotwater_program_param: <parameter definition for the hotwater control program>
  device: # connection and device specific configuration
    name: <device_name>
    type: serial # may be set to 'dummy' for testing purposes
    serial_device: /dev/ttyUSB0 # linux serial device node
    protocol: KW # other protocols may also be implemented later
    parameters: # this contains a list of every parameter, its address and the encoding used
      - param: <parameter_configuration>
        encoding: <encoding_configuration>
        address: <numeric address of the parameter within the heating control>
      ...
```

It is recommended to use yaml anchors and aliases for not having to repeatedly define the same parameters when they are used at different places within the configuration.

*config.yaml*
```yaml
parameters:
  - &cpr_a1 # define anchor
    id: control_program_circuit_a1
    name: Control program A1
    unit: *control_program
    readonly: false
  - &cpr_water # define another anchor
    id: control_program_hotwater
    name: Schaltprogramm Warmwasser
    unit: *control_program
    readonly: false
  ...

config:
  ...
  device:
    ...
    parameters:
      - param: *cpr_a1 # use anchor
        ...
      - param: *cpr_water # use anchor
        ...
      ...
  api:
    highlevel:
      hotwater_control_param: *cpr_water # the same anchor is used twice
```

## API
Completely JSON oriented. Parameters are expected to be given in `application/json` and returned values are always `application/json`.

***
**Overview**
### Authentication related
- [POST `/auth/login`](#auth_login) Login and request access token
### Control programs
- [GET `/programs`](#programs) Get list of control programs
- [GET `/programs/<program_id>`](#programs_program) Get info about specific control program
- [GET `/programs/<program_id>/reload`](#programs_program_reload) - Reload control program from heating device
- [GET `/programs/<program_id>/day/<day_id>`](#programs_day) Get control program for specific day
- [GET `/programs/<program_id>/day/<day_id>/reload`](#programs_day_reload) Reload specific day
- [POST `/programs/<program_id>/day/<day_id>`](#post_programs_day) Change control program for a specific day
### Parameters
- [GET `/parameters`](#parameters) Get an overview over defined parameters
- [GET `/parameters/<parameter_id>`](#parameters_param) Get a specific parameter's value
- [POST `/parameters/<parameter_id>`](#post_parameters_param) Set the value of a specific parameter
- [GET `/parameters/<parameter_id>/reload`](#parameters_param_reload) Reload a parameter's value
### Raw byte access
- [GET `/raw/<hex_address>/<byte_count>`](#raw_read) Get raw bytes stored at a given address
***
<a name="auth_login"></a>

### **POST** `/auth/login`
- Request payload:
  ```json
  {
    "user": "<username>",
    "password": "<password>"
  }
  ```
- Response:
  - If login was successful:
    **Status 200**
    ```json
    {
      "token": "127c81d1e8d4a8cd9a6f10068def3959",
      "valid_until": "2021-02-26T19:31:16.959047"
    }
    ```
    The returned token should be sent with each following request by using the `Authorization: Bearer <token>` HTTP header.
  - On Failure:
    **Status 401**
    ```json
    {"error": "Authentication failed!"}
    ```
    or some more specific error message.

***
<a name="programs"></a>

### **GET** `/programs`
Get a list of control programs which can be read or set.
- (Example) response:
  ```json
  [
    {"id": "control_program_hotwater", "name": "Hotwater control program"},
    {"id": "control_program_a1", "name": "Heating circuit A1 control program"},
    {"id": "control_program_m2", "name": "Heating circuit M2 control program"}
  ]
  ```

***
<a name="programs_program"></a>

### **GET** `/programs/<program_id>`
Show the control program for `program_id`.
- Response:
  ```json
  {
    "id": "control_program_a1",
    "name": "Heating circuit A1 control program",
    "lastReload": "2020-11-23T07:10:44.052060",
    "cycleTimes": [
      {
        "dayID": 0,
        "dayName": "Monday",
        "lastReload": "2020-11-23T07:10:44.052060",
        "cycleTimes": [
          {"on": "06:00", "off": "08:00"}, 
          {"on": "17:00", "off": "20:00"}
        ]
      },
      {
        "dayID": 1,
        "dayName": "Tuesday",
        "lastReload": "2020-11-23T07:10:44.052060",
        "cycleTimes": [
          {"on": "06:00", "off": "08:00"}
        ]
      },
      ...
    ]
  }
  ```

***
<a name="programs_program_reload"></a>

### **GET** `/programs/<program_id>/reload`
Does the same as `/programs/<program_id>` but forces reloading the control program from the heating control unit (bypassing cached values).

***
<a name="programs_day"></a>

### **GET** `/programs/<program_id>/day/<day_id>`
Show the control program for day `day_id` in program `program_id`. `day_id` is the weekday as an integer, where 0 indicates Monday, 1 indicates Tuesday and so on.
- Response:
  ```json
  {
    "dayID": 0,
    "dayName":"Monday",
    "lastReload":"2020-11-28T19:50:00.888680",
    "cycleTimes": [
      {"on": "06:00","off": "08:00"},
      {"on": "17:00", "off": "20:00"}
    ]
  }
  ```
`lastReload` indicates when the control program has been last read from the heating control unit.

***
<a name="programs_day_reload"></a>

### **GET** `/programs/<program_id>/day/<day_id>/reload`
Does the same as `/programs/<program_id>/day/<day_id>` but forces reloading the control program of the given day from the heating control unit (bypassing cached values).

***
<a name="post_programs_day"></a>

### **POST** `/programs/<program_id>/day/<day_id>`
Sets the control program for the given day.
- Request payload:
  ```json
  [
    {"on": "06:30", "off": "09:00"},
    {"on": "11:00", "off": "13:00"}
  ]
  ```
  The request contains an array up to 4 shifting intervals (defined by `on/off`) which have
  to be ordered chronologically and also may not overlap.

- Response (on success):
  ```json
  {"success": true}
  ```

***
<a name="parameters"></a>

### **GET** `/parameters`
Gets a list of all parameters defined for the heating control unit.
- (Exemplary) response:
  ```json
  [
    {
      "id": "temp_outside",
      "title": "Outside temperature",
      "readonly":true,
      "unit": {
        "type": "number",
        "integral": false,
        "min": -30,
        "max": 50,
        "suffix": ""
      }
    },
    {
      "id": "control_program_hotwater",
      "title": "Control program hotwater",
      "readonly": false,
      "unit": {
        "type": "timer"
      }
    },
    {
      "id": "status_burner",
      "title": "Burner status",
      "readonly": true,
      "unit": {
        "type": "enum",
        "possible_values": [
          {"value": 0, "text": "Off"},
          {"value": 1, "text": "On"}
        ]
      }
    },
    {
      "id": "nominal_temp_red_a1",
      "title": "Reduced nominal room temperature A1",
      "readonly": false,
      "unit": {
        "type": "number",
        "integral": true,
        "min": 3,
        "max": 37,
        "suffix": "°C"
      }
    },
    ...
  ]
  ```

***
<a name="parameters_param"></a>

### **GET** `/parameters/<parameter_id>`
Read the value of a parameter.
- (Exemplary) response
  ```json
  {
    "id": "temp_outside",
    "name": "Outside temperature",
    "lastReload": "2020-12-01T21:24:15.149452",
    "value": 0.0,
    "display_string": "0.0°C",
    "readonly": true,
    "unit": {
      "type": "number",
      "integral": false,
      "min": -30,
      "max": 50,
      "suffix": "°C"
    }
  }


***
<a name="post_parameters_param"></a>

### **POST** `/parameters/<parameter_id>`
Set the value of a parameter.
- (Exemplary) request payload: set the nominal room temperature to 23 degree Celsius
  ```json
  23
  ```
The request payload only contains the value of the parameter.
***
<a name="parameters_param_reload"></a>

### **GET** `/parameters/<parameter_id>/reload`
Does the same as [`/parameters/<parameter_id>`](#parameters_param) but forces reloading the parameter value from the heating control unit (bypassing cached values).

***
<a name="raw_read"></a>

### **GET** `/raw/<hex_address>/<byte_count>`
- No parameters, just read `byte_count` Bytes from `hex_address`. E. g. for getting the device ID you would call `/raw/00f8/2`
- Response (for a Vitotronic 200KW2 unit):
  ```json
  {
    "address": "00f8",
    "size": 2,
    "value": "0x2098"
  }
  ```
