import base64
from json import JSONEncoder
from typing import Any

import numpy as np

from cltl.backend.api.camera import Image, Bounds


class NumpyJSONEncoder(JSONEncoder):
    def __init__(self, *, delegate: JSONEncoder = None, **kwargs):
        super().__init__(**kwargs)
        self._delegate = delegate

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return {
                "__type": "np.ndarray",
                "data": base64.b64encode(obj.tobytes()).decode('ascii'),
                "shape": obj.shape,
                "dtype": str(obj.dtype)
            }

        return self._delegate.default(obj) if self._delegate else super().default(obj)


class BackendJSONEncoder(NumpyJSONEncoder):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def default(self, obj):
        if isinstance(obj, Image):
            return vars(obj)
        if isinstance(obj, Bounds):
            return [obj.x0, obj.x1, obj.y0, obj.y1]

        return super().default(obj)


def numpy_object_hook(obj):
    if not isinstance(obj, dict) or "__type" not in obj or obj["__type"] != "np.ndarray":
        return obj

    data_string = obj["data"]
    shape = obj["shape"]
    dtype = obj["dtype"]

    return np.frombuffer(base64.b64decode(data_string), dtype=dtype).reshape(shape)


def image_hook(json_data: Any) -> Image:
    image = numpy_object_hook(json_data['image'])
    try:
        view = Bounds(**json_data['view'])
    except TypeError:
        view = Bounds(*json_data['view'])
    depth = numpy_object_hook(json_data['depth'])

    return Image(image, view, depth)