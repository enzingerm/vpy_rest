from typing import Union as UnionType


def _identity(val):
    return val


_obj = object()


class NestedException(Exception):
    def __init__(self, context: str, inner: Exception = None, message: str = ""):
        self.context = [context]
        if isinstance(inner, NestedException):
            self.context += inner.context
            self.message = inner.message
        else:
            self.message = message

    def __str__(self):
        return "At " + " > ".join(self.context) + ": " + self.message


class InvalidTypeException(Exception):
    def __init__(self, expected=None, given=None):
        self.expected = expected
        self.given = given


class AbsentDefaultValueException(Exception):
    pass


class ConfigException(Exception):
    pass


class InvalidOptionException(Exception):
    def __init__(self, value):
        self.value = value


class BaseParsedValueContainer:
    def __init__(self, value):
        self._value = value

    def get(self):
        raise NotImplementedError


class ParsedNamespace(BaseParsedValueContainer):
    def get(self):
        return {
            name: it.get() if isinstance(it, BaseParsedValueContainer) else it
            for name, it in self._value.items()
        }

    def __getattr__(self, name):
        if name in self._value:
            return self._value[name]
        raise AttributeError(name)

    def __getitem__(self, name):
        if name in self._value:
            return self._value[name]
        raise KeyError(name)


class ParsedAlternative(BaseParsedValueContainer):
    def __init__(self, discriminant_value, option_value):
        super().__init__((discriminant_value, option_value))

    def get(self):
        return (
            self._value[0],
            self._value[1].get()
            if isinstance(self._value[1], BaseParsedValueContainer)
            else self._value[1],
        )

    def __getattr__(self, name):
        if name == "option_value":
            return self._value[0]
        return getattr(self._value[1], name)


class ParsedList(BaseParsedValueContainer):
    def get(self):
        return [
            it.get() if isinstance(it, BaseParsedValueContainer) else it
            for it in self._value
        ]

    def __len__(self):
        return len(self._value)

    def __getitem__(self, item):
        if not isinstance(item, int) or 0 > item or item >= len(self._value):
            raise IndexError(item)
        return self._value[item]


class Value:
    def __init__(self, default=_obj, mapper=_identity):
        self.default = default
        self.mapper = mapper

    def get_val(self, val):
        if self.default == _obj and val == _obj:
            raise AbsentDefaultValueException
        if val != _obj:
            return val
        return self.default

    def parse(self, val):
        return self.mapper(self.get_val(val))


class Union(Value):
    def __init__(self, section=None, lst=None, val=None, default=_obj):
        super().__init__(default)
        self.section = section
        self.list = lst
        self.val = val

    def parse(self, val):
        val = self.get_val(val)
        chosen_type = self.val
        if isinstance(val, dict):
            chosen_type = self.section
        elif isinstance(val, list):
            chosen_type = self.list

        assert chosen_type is not None, "No applicable union type member found!"
        return chosen_type.parse(val)


class NamedContainer(Value):
    def __init__(
        self,
        children: dict,
        default=_obj,
        mapper=_identity,
        propagate_single_value=False,
    ):
        super().__init__(default, mapper)
        self.children = children
        self.propagate_single_value = propagate_single_value

    def parse(self, val):
        val = self.get_val(val)
        if not isinstance(val, dict):
            raise InvalidTypeException("dict", type(val).__name__)
        ret = {}
        for name, child in self.children.items():
            try:
                if isinstance(child, Alternative):
                    ret[name] = child.parse((val.get(name, _obj), val))
                else:
                    ret[name] = child.parse(val.get(name, _obj))
            except AbsentDefaultValueException:
                raise NestedException(
                    name, message=f"No default value given for {name}!"
                )
            except InvalidTypeException as e:
                raise NestedException(
                    name,
                    message=f"Invalid argument type{' <' + e.given + '>' if e.given else ''}"
                    f" given to option '{name}'{', expected <' + str(e.expected) + '>' if e.expected else ''}!",
                )
            except InvalidOptionException as e:
                raise NestedException(
                    name, message=f"Invalid option provided to {name}: {e.value}"
                )
            except NestedException as e:
                raise NestedException(name, e)
        if len(ret) == 1 and self.propagate_single_value:
            # propagate single value
            return self.mapper([*ret.values()][0])
        return self.mapper(ParsedNamespace(ret))

    def get_indices(self):
        return self.children.keys()


class Config(NamedContainer):
    def apply_config(self, cfg):
        try:
            return self.parse(cfg)
        except NestedException as e:
            print("Configuration error: " + str(e))
            raise
        except ConfigException as e:
            print("Configuration error: " + e.args[0])
            raise


class Section(NamedContainer):
    pass


class Alternative(Value):
    def __init__(self, *options, mapper=_identity, hide_discriminant=True):
        super().__init__(mapper=mapper)
        self.options = options
        self.chosen_option = None
        self.hide_discriminant = hide_discriminant

    def parse(self, val):
        discriminator_val, complete = val
        if isinstance(discriminator_val, (dict, list)):
            raise InvalidTypeException
        self.chosen_option = self._resolve_option(discriminator_val)
        if self.chosen_option is None:
            raise AbsentDefaultValueException

        option_val = self.chosen_option.parse(
            {k: complete[k] for k in self.chosen_option.get_indices() if k in complete}
        )
        # if hide_discriminant, just return the value returned by the option
        if self.hide_discriminant:
            return self.mapper(option_val)
        return self.mapper(ParsedAlternative(self.chosen_option.value, option_val))

    def _resolve_option(self, val):
        for option in self.options:
            if option.value == val:
                return option

        if val != _obj:
            # value given, but matched no option
            raise InvalidOptionException(val)

        default_options = [o for o in self.options if o.default_option]
        assert (
            len(default_options) < 2
        ), "Multiple default options given for alternative!"
        try:
            return default_options[0]
        except IndexError:
            return None


class Option(NamedContainer):
    def __init__(
        self,
        value,
        children: dict = {},
        default_option=False,
        default=None,
        mapper=_identity,
    ):
        super().__init__(children, default, mapper)
        if any(isinstance(v, Alternative) for v in children.values()):
            raise ConfigException(
                "Alternatives may not be nested, use a Section in between!"
            )
        self.default_option = default_option
        self.value = value


class List(Value):
    def __init__(
        self,
        child_type: UnionType[dict, Value],
        default=_obj,
        mapper=_identity,
        child_mapper=_identity,
    ):
        super().__init__(default, mapper)
        if isinstance(child_type, dict):
            self.child_type = Section(child_type, mapper=child_mapper)
        else:
            self.child_type = child_type

    def parse(self, val):
        val = self.get_val(val)
        if not isinstance(val, list):
            raise InvalidTypeException("List", type(val).__name__)
        return self.mapper(ParsedList([self.child_type.parse(v) for v in val]))

