import json

import pytest

import helper


@pytest.mark.parametrize('data,expected', (
    ({}, b'\x00\x02{}'),
    ({'a': 1}, b'\x00\x08{"a": 1}'),
    ({
        'brown': 'fox',
        'z': {
            'alpha': 'ž',
        },
    }, b'\x00*{"brown": "fox", "z": {"alpha": "\\u017e"}}'),
))
def test_encode_json(data, expected):
    assert helper.encode_json(data) == expected