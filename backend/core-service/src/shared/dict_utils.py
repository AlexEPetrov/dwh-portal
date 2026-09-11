from collections import namedtuple


def dict_to_namedtuple(typename, data):
    return namedtuple(typename, data.keys())(
        *(dict_to_namedtuple(typename + '_' + k, v) if isinstance(v, dict) else v for k, v in data.items())
    )  