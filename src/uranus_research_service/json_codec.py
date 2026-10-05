"""Reject ambiguous JSON and nonfinite constants at both HTTP boundaries."""

import json


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("nonfinite_json")


def decode(value: bytes):
    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant)
