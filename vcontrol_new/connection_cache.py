from datetime import datetime, timedelta
from typing import Any, Union

from .connection import ViessmannConnection
from .parameter import AggregatedParameter, Parameter, ParameterReading


class ConnectionCache:
    """Proxy class wrapping a `ViessmannConnection` and caching values."""

    def __init__(self, conn: ViessmannConnection):
        self.conn = conn
        self.values = dict()

    @property
    def param_storage(self):
        return self.conn.param_storage

    async def read_param(
        self,
        param: Union[Parameter, str],
        force: bool = False,
        max_age_seconds: int = -1,
    ) -> ParameterReading:
        """Read a parameter value from the heating control device or from the cache.

        The normal behaviour is that if a cached value is present, it is returned, otherwise
        the value is read directly from the heating control device. Re-reading the value can
        be forced by parameters `force` or `max_age_seconds`.
        """
        param_id = param if isinstance(param, str) else param.id
        current_reading = self._get_reading(param_id)
        must_reload = (
            not current_reading
            or force
            or max_age_seconds > 0
            and current_reading.time
            < datetime.now() - timedelta(seconds=max_age_seconds)
        )
        if not must_reload:
            return current_reading
        # now reload
        param_to_load = self.conn.get_param(param_id)
        self.values[param_id] = await self.conn.read_param(param_to_load)
        self._invalidate_children(param_to_load)
        return self.values[param_id]

    async def set_param(self, param: Union[Parameter, str], value: Any):
        """Write a value to the heating control device and cache it for later requests."""
        param_to_set = self.conn.get_param(
            param if isinstance(param, str) else param.id
        )
        await self.conn.set_param(param_to_set, value)
        # if set_param() completed without an error, assume the value has been written
        # to the device
        self.values[param_to_set.id] = ParameterReading.create_now(param_to_set, value)
        self._invalidate_children(param_to_set)
        # invalidate parent if child param was set
        if "." in param_to_set.id:
            container = param_to_set.id.split(".")[0]
            if container in self.values:
                del self.values[container]

    def _get_reading(self, param_id: str):
        if param_id in self.values:
            return self.values[param_id]
        if "." in param_id:
            container, index = param_id.split(".")
            if container in self.values:
                container_reading = self.values[container]
                return ParameterReading(
                    container_reading.parameter.get_child_param(int(index)),
                    container_reading.value[int(index)],
                    container_reading.time,
                )
        return None

    def _invalidate_children(self, param: Parameter):
        if isinstance(param, AggregatedParameter):
            for index in range(param.child_count):
                try:
                    del self.values[f"{param.id}.{index}"]
                except KeyError:
                    pass
