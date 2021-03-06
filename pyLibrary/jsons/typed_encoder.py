# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#



from collections import deque

import json
import re
import time
from datetime import datetime, date, timedelta
from decimal import Decimal
from pyLibrary.debugs.logs import Log

from pyLibrary.dot import Dict, DictList, NullType
from pyLibrary.jsons import ESCAPE_DCT
from pyLibrary.jsons.encoder import \
    pretty_json, \
    problem_serializing, \
    _repr, \
    UnicodeBuilder
from pyLibrary.maths.stats import Stats
from pyLibrary.strings import utf82unicode
from pyLibrary.times.dates import Date
from pyLibrary.times.durations import Duration


json_decoder = json.JSONDecoder().decode

append = UnicodeBuilder.append
_ = Stats

def typed_encode(value):
    """
    pypy DOES NOT OPTIMIZE GENERATOR CODE WELL
    """
    try:
        _buffer = UnicodeBuilder(1024)
        _typed_encode(value, _buffer)
        output = _buffer.build()
        return output
    except Exception as e:
        # THE PRETTY JSON WILL PROVIDE MORE DETAIL ABOUT THE SERIALIZATION CONCERNS
        from pyLibrary.debugs.logs import Log

        Log.warning("Serialization of JSON problems", e)
        try:
            return pretty_json(value)
        except Exception as f:
            Log.error("problem serializing object", f)


def _typed_encode(value, _buffer):
    try:
        if value is None:
            append(_buffer, '{"$value": null}')
            return
        elif value is True:
            append(_buffer, '{"$value": true}')
            return
        elif value is False:
            append(_buffer, '{"$value": false}')
            return

        _type = value.__class__
        if _type in (dict, Dict):
            if value:
                _dict2json(value, _buffer)
            else:
                append(_buffer, '{"$object": "."}')
        elif _type is str:
            append(_buffer, '{"$value": "')
            try:
                v = utf82unicode(value)
            except Exception as e:
                problem_serializing(value, e)

            for c in v:
                append(_buffer, ESCAPE_DCT.get(c, c))
            append(_buffer, '"}')
        elif _type is str:
            append(_buffer, '{"$value": "')
            for c in value:
                append(_buffer, ESCAPE_DCT.get(c, c))
            append(_buffer, '"}')
        elif _type in (int, int, Decimal):
            append(_buffer, '{"$value": ')
            append(_buffer, str(value))
            append(_buffer, '}')
        elif _type is float:
            append(_buffer, '{"$value": ')
            append(_buffer, str(repr(value)))
            append(_buffer, '}')
        elif _type in (set, list, tuple, DictList):
            _list2json(value, _buffer)
        elif _type is date:
            append(_buffer, '{"$value": ')
            append(_buffer, str(int(time.mktime(value.timetuple()))))
            append(_buffer, '}')
        elif _type is datetime:
            append(_buffer, '{"$value": ')
            append(_buffer, str(int(time.mktime(value.timetuple()))))
            append(_buffer, '}')
        elif _type is Date:
            append(_buffer, '{"$value": ')
            append(_buffer, str(int(time.mktime(value.value.timetuple()))))
            append(_buffer, '}')
        elif _type is timedelta:
            append(_buffer, '{"$value": ')
            append(_buffer, str(value.total_seconds()))
            append(_buffer, '}')
        elif _type is Duration:
            append(_buffer, '{"$value": ')
            append(_buffer, str(value.seconds))
            append(_buffer, '}')
        elif _type is NullType:
            append(_buffer, "null")
        elif hasattr(value, '__json__'):
            j = value.__json__()
            t = json2typed(j)
            append(_buffer, t)
        elif hasattr(value, '__iter__'):
            _iter2json(value, _buffer)
        else:
            from pyLibrary.debugs.logs import Log

            Log.error(_repr(value) + " is not JSON serializable")
    except Exception as e:
        from pyLibrary.debugs.logs import Log

        Log.error(_repr(value) + " is not JSON serializable", e)


def _list2json(value, _buffer):
    if not value:
        append(_buffer, "[]")
    else:
        sep = "["
        for v in value:
            append(_buffer, sep)
            sep = ", "
            _typed_encode(v, _buffer)
        append(_buffer, "]")


def _iter2json(value, _buffer):
    append(_buffer, "[")
    sep = ""
    for v in value:
        append(_buffer, sep)
        sep = ", "
        _typed_encode(v, _buffer)
    append(_buffer, "]")


def _dict2json(value, _buffer):
    prefix = '{"$object": ".", "'
    for k, v in value.items():
        append(_buffer, prefix)
        prefix = ", \""
        if isinstance(k, str):
            k = utf82unicode(k)
        if not isinstance(k, str):
            Log.error("Expecting property name to be a string")
        for c in k:
            append(_buffer, ESCAPE_DCT.get(c, c))
        append(_buffer, "\": ")
        _typed_encode(v, _buffer)
    append(_buffer, "}")


VALUE = 0
PRIMITIVE = 1
BEGIN_OBJECT = 2
OBJECT = 3
KEYWORD = 4
STRING = 6
ESCAPE = 5


def json2typed(json):
    """
    every ': {' gets converted to ': {"$object": ".", '
    every ': <value>' gets converted to '{"$value": <value>}'
    """
    # MODE VALUES
    #

    context = deque()
    output = UnicodeBuilder(1024)
    mode = VALUE
    for c in json:
        if c in "\t\r\n ":
            append(output, c)
        elif mode == VALUE:
            if c == "{":
                context.append(mode)
                mode = BEGIN_OBJECT
                append(output, '{"$object": "."')
                continue
            elif c == '[':
                context.append(mode)
                mode = VALUE
            elif c == ",":
                mode = context.pop()
                if mode != OBJECT:
                    context.append(mode)
                    mode = VALUE
            elif c in "]":
                mode = context.pop()
            elif c in "}":
                mode = context.pop()
                mode = context.pop()
            elif c == '"':
                context.append(mode)
                mode = STRING
                append(output, '{"$value": ')
            else:
                mode = PRIMITIVE
                append(output, '{"$value": ')
            append(output, c)
        elif mode == PRIMITIVE:
            if c == ",":
                append(output, '}')
                mode = context.pop()
                if mode == 0:
                    context.append(mode)
            elif c == "]":
                append(output, '}')
                mode = context.pop()
            elif c == "}":
                append(output, '}')
                mode = context.pop()
                mode = context.pop()
            append(output, c)
        elif mode == BEGIN_OBJECT:
            if c == '"':
                context.append(OBJECT)
                context.append(KEYWORD)
                mode = STRING
                append(output, ', ')
            elif c == "}":
                mode = context.pop()
            else:
                Log.error("not expected")
            append(output, c)
        elif mode == KEYWORD:
            append(output, c)
            if c == ':':
                mode = VALUE
            else:
                Log.error("Not expected")
        elif mode == STRING:
            append(output, c)
            if c == '"':
                mode = context.pop()
                if mode != KEYWORD:
                    append(output, '}')
            elif c == '\\':
                context.append(mode)
                mode = ESCAPE
        elif mode == ESCAPE:
            mode = context.pop()
            append(output, c)
        elif mode == OBJECT:
            if c == '"':
                context.append(mode)
                context.append(KEYWORD)
                mode = STRING
            elif c == ",":
                pass
            elif c == '}':
                mode = context.pop()
            else:
                Log.error("not expected")

            append(output, c)

    if mode == PRIMITIVE:
        append(output, "}")
    return output.build()

