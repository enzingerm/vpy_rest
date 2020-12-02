# Configuration parsing library

## Quick How-To

1. The structure of the configuration is defined in a hierarchical way by creating
   a DSL-like object hierarchy.
    ```python
    config = Config({
        "server": Section({
            "ip": Value(default="127.0.0.1"),
            "port": Value(8000)
        }),
        "auth": Section({
            "provider": Alternative(
                Option("none", default_option=True),
                Option("token", {
                    "token_validity_days": Value(default=90),
                    "allowed_users": List({
                        "username": Val(),
                        "password": Val(default="secret")
                    })
                })
            )
        })
    })
    ```
2. A parsed configuration in form of a hierarchical structure of `dict`s, `list`s and
   primitive values, e.g. from a parsed YAML file is applied to the configuration
   definition, resulting in a parsed configuration which then can be used to drive
   the program.
   ```python
   parsed_config = {
       "server": {
           "ip": "0.0.0.0"
       },
       "auth": {
           "provider": "token",
           "allowed_users": [
               {"username": "john", "password": "password"},
               {"username": "eric"}
           ]
       }
   }

   final_config = config.apply_config(parsed_config)

   final_config.server.ip                               # "0.0.0.0"
   final_config.server.port                             # 8000
   final_config.auth.provider.allowed_users[1].password # "secret"
   ```

# API
### `Value([default=<default>])`
represents a primitive value like a String or a number.
  

### `Section()`
is the equivalent of a python `dict` and represents a mapping of names to values.
The base `Config()` can also be used just like a section.
```python
cfg = Config({
    "section_a": Section({
        "inner_section": Section({
            "option": Value()
        })
    }),
    "section_b": Section({
        "option_b": Value()
    })
})
# this matches a config like the following:
cfg.apply_config({
    "section_a": {
        "inner_section": { "option": 1 }
    },
    "section_b": { "option_b": 2 }
})
```
### `List()`
is the equivalent of a python `list` and can contain different objects.
```python
config = Config({
    "list_of_primitives": List(Value()),
    "list_of_structured_objects": List({
        "option_a": Value(),
        "option_b": Value()
    }),
    "list_of_lists": List(List(Value()))
})
```

### `Alternative()` and `Option()`
match different sub-sections of a config based on a discriminant value.
```python
config = Config({
    "value_provider": Alternative(
        Option("option_a", {
            "param_for_a": Value()
        }, default_option=True),
        Option("option_b", {
            "param_for_b": Value()
        })
    )
})

cfg1 = config.apply_config({
    "value_provider": "option_a",
    "param_for_a": 123
})
cfg1.value_provider.param_for_a         # 123

cfg2 = config.apply_config({
    "value_provider": "option_b",
    "param_for_b": "test_value"
})
cfg2.value_provider.param_for_b         # "test_value"

cfg3 = config.apply_config({
    "some_other_param": 123
})
# Raises "At value_provider > param_for_a: No default value given for param_for_a!"
```

## Mappers
Each configuration directive can have a mapper function applied to it. This function
gets the parsed configuration as its first parameter and its return value is then returned
when accessing the configuration object.
```python
cfg = Config({
    "sum_of_powers": List(
        Section({
            "value": Value(),
            "power": Value(default=1)
        }, mapper=lambda x: x.value ** x.power),
        mapper=sum
    )
})
cfg.apply_config({
    "sum_of_powers": [
        {"value" 1},
        {"value": 2, "power": 2},
        {"value": 3}
    ]
}).sum_of_powers        # 8
```
_Sidenote:_ These two variants for lists are equivalent:
```python
List(
    Section({
        ...
    }, mapper=...)
)
List({
    ...
}, child_mapper=...)
```
