from typing import Dict, List, Tuple, Union

from .encoding import Encoding
from .parameter import AggregatedParameter, Parameter
from .protocol import KWProtocol, Protocol
from collections import namedtuple

ParamMapping = namedtuple("ParamMapping", ["param", "encoding", "address"])


class ParameterStorage:
    """
    Provides information about location (address) and format (encoding) of
    a heating control's parameters
    """

    def __init__(self):
        self.parameters: Dict[str, Tuple[Parameter, bytes, Encoding]] = dict()

    def add_parameter(self, parameter: Parameter, address: bytes, encoding: Encoding):
        if parameter.id in self.parameters:
            raise Exception("Parameter already exists")
        self.parameters[parameter.id] = parameter, address, encoding

    def get_supported_parameters(self) -> List[Parameter]:
        return [param for param, _, _ in self.parameters.values()]

    def get_storage(self, param: Union[str, Parameter]):
        param_id = param if isinstance(param, str) else param.id
        # if a child parameter is wanted, delegate
        if "." in param_id:
            container, index = param_id.split(".")
            return self.get_child_storage(container, int(index))
        return self.parameters[param_id]

    def get_parameter(self, param_id: str):
        return self.get_storage(param_id)[0]

    def get_child_storage(self, param: Union[str, AggregatedParameter], index: int):
        assert not isinstance(param, str) or not "." in param
        param_id = param if isinstance(param, str) else param.id
        container_param, container_address, container_encoding = self.parameters[
            param_id
        ]
        if index >= container_param.child_count:
            raise IndexError("Child parameter index out of range!")
        param = container_param.get_child_param(index)
        encoding = container_encoding.member_encoding
        address = (
            int.from_bytes(container_address, "big", signed=False)
            + encoding.get_size() * index
        ).to_bytes(len(container_address), "big", signed=False)
        return param, address, encoding


class BaseHeatingControl:
    """Represents a heating control device.

    A heating device has a list of associated with it, which can be read from or written to.
    It also provides a protocol which should be used for communication with the device.
    """

    def __init__(self):
        self.storage = ParameterStorage()

    def get_param_storage(self):
        return self.storage

    def get_protocol(self) -> Protocol:
        raise NotImplementedError

    def get_supported_parameters(self) -> List[Parameter]:
        return self.storage.get_supported_parameters()


class HeatingControl(BaseHeatingControl):
    def __init__(self, param_mappings: List[ParamMapping], protocol):
        super().__init__()
        self.protocol = protocol
        for param_mapping in param_mappings:
            self.storage.add_parameter(
                param_mapping.param, param_mapping.address, param_mapping.encoding
            )

    def get_protocol(self):
        if self.protocol == "KW":
            return KWProtocol()
        else:
            raise Exception("Unsupported protocol given!")
