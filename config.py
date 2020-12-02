from datetime import timedelta

import yaml

from api.auth import (
    DummyAuthenticationBackend,
    ListAuthenticationBackend,
    NoAuthenticationProvider,
    TokenAuthenticationProvider,
)
from api.metrics import MetricMapping
from util.config import *
from vcontrol_new import (
    ConnectionCache,
    HeatingControl,
    OptolinkConnection,
    ParamMapping,
    ViessmannConnection,
)
from vcontrol_new.dummy import HeatingDummy
from vcontrol_new.encoding import (
    ArrayEncoding,
    FloatEncoding,
    IntEncoding,
    SystemTimeEncoding,
    TimerEncoding,
)
from vcontrol_new.parameter import AggregatedParameter, Parameter
from vcontrol_new.unit import (
    CycleTimeUnit,
    HourUnit,
    NumberUnit,
    OperatingStatusUnit,
    SystemTimeUnit,
)

param_config = Section(
    {
        "id": Value(),
        "name": Value(),
        "unit": Section(
            {
                "type": Alternative(
                    Option(
                        "number",
                        {
                            "min": Value(default=None),
                            "max": Value(default=None),
                            "integer": Value(default=False),
                            "suffix": Value(default=""),
                        },
                        mapper=lambda x: NumberUnit(x.min, x.max, x.integer, x.suffix),
                    ),
                    Option("operating_status", mapper=lambda x: OperatingStatusUnit()),
                    Option("system_time", mapper=lambda x: SystemTimeUnit()),
                    Option(
                        "array",
                        {
                            "length": Value(),
                            "child": Section(
                                {"type": Alternative(Option("control_program_day"))}
                            ),
                        },
                        mapper=lambda x: {"length": x.length, "unit": CycleTimeUnit()},
                    ),
                    Option("hour", mapper=lambda x: HourUnit()),
                    hide_discriminant=True,
                )
            },
            propagate_single_value=True,
        ),
        "readonly": Value(default=True),
    },
    mapper=lambda x: Parameter(x.name, x.id, x.unit, x.readonly)
    if not isinstance(x.unit, dict)
    else AggregatedParameter(
        x.name, x.id, x.unit["unit"], x.unit["length"], x.readonly
    ),
)


def create_kerberos_auth(section):
    from api.auth.kerberos import KerberosAuthenticationBackend

    return KerberosAuthenticationBackend(
        section.realm, allowed_users={user for user in section.allowed_users}
    )


def get_config(loop, file: str = "config.yaml"):
    config = Config(
        {
            "server": Section(
                {"ip": Value(default="127.0.0.1"), "port": Value(default=8000)}
            ),
            "device": Section(
                {
                    "name": Value(default="Dummy"),
                    "type": Alternative(
                        Option("dummy", mapper=lambda x: HeatingDummy(loop)),
                        Option(
                            "serial",
                            {"serial_device": Value(default="/dev/ttyUSB0")},
                            mapper=lambda x: OptolinkConnection(loop, x.serial_device),
                            default_option=True,
                        ),
                        hide_discriminant=True,
                    ),
                    "protocol": Value(default="KW"),
                    "parameters": List(
                        {
                            "param": param_config,
                            "encoding": Section(
                                {
                                    "type": Alternative(
                                        Option(
                                            "float",
                                            {"size": Value(), "factor": Value()},
                                            mapper=lambda x: FloatEncoding(
                                                x.size, x.factor
                                            ),
                                        ),
                                        Option(
                                            "int",
                                            {"size": Value()},
                                            mapper=lambda x: IntEncoding(x.size),
                                        ),
                                        Option(
                                            "system_time",
                                            mapper=lambda x: SystemTimeEncoding(),
                                        ),
                                        Option(
                                            "array",
                                            {
                                                "length": Value(),
                                                "child": Section(
                                                    {
                                                        "type": Alternative(
                                                            Option(
                                                                "control_program_day"
                                                            )
                                                        )
                                                    }
                                                ),
                                            },
                                            mapper=lambda x: ArrayEncoding(
                                                TimerEncoding(), x.length
                                            ),
                                        ),
                                        hide_discriminant=True,
                                    )
                                },
                                propagate_single_value=True,
                            ),
                            "address": Value(
                                mapper=lambda x: x.to_bytes(2, byteorder="big")
                            ),
                        },
                        child_mapper=lambda x: ParamMapping(
                            x.param, x.encoding, x.address
                        ),
                    ),
                },
                mapper=lambda x: ConnectionCache(
                    ViessmannConnection(
                        HeatingControl(x.parameters, x.protocol), x.type
                    )
                ),
            ),
            "api": Section(
                {
                    "auth": Section(
                        {
                            "provider": Alternative(
                                Option(
                                    "none",
                                    default_option=True,
                                    mapper=lambda x: NoAuthenticationProvider(
                                        DummyAuthenticationBackend()
                                    ),
                                ),
                                Option(
                                    "token",
                                    {
                                        "token_validity_days": Value(default=90),
                                        "backend": Section(
                                            {
                                                "type": Alternative(
                                                    Option(
                                                        "dummy",
                                                        default_option=True,
                                                        mapper=lambda x: DummyAuthenticationBackend(),
                                                    ),
                                                    Option(
                                                        "list",
                                                        {
                                                            "users": List(
                                                                {
                                                                    "username": Value(),
                                                                    "password": Value(
                                                                        default="secret"
                                                                    ),
                                                                }
                                                            )
                                                        },
                                                        mapper=lambda x: ListAuthenticationBackend(
                                                            x.users.get()
                                                        ),
                                                    ),
                                                    Option(
                                                        "kerberos",
                                                        {
                                                            "realm": Value(),
                                                            "allowed_users": List(
                                                                Value()
                                                            ),
                                                        },
                                                        mapper=create_kerberos_auth,
                                                    ),
                                                    hide_discriminant=True,
                                                )
                                            }
                                        ),
                                    },
                                    mapper=lambda x: TokenAuthenticationProvider(
                                        x.backend.type,
                                        timedelta(days=x.token_validity_days),
                                    ),
                                ),
                                hide_discriminant=True,
                            )
                        }
                    ),
                    "prometheus_metrics": Section(
                        {
                            "enabled": Value(default=False),
                            "mappings": List(
                                {
                                    "param": param_config,
                                    "prometheus_name": Value(),
                                    "type": Value(),
                                },
                                child_mapper=lambda x: MetricMapping(
                                    x.param, x.prometheus_name, x.type
                                ),
                                mapper=lambda x: x.get(),
                            ),
                        }
                    ),
                    "highlevel": Section({"hotwater_program_param": param_config}),
                }
            ),
        }
    )
    with open(file, "r") as stream:
        parsed_cfg = config.apply_config(yaml.safe_load(stream)["config"])

    return parsed_cfg
