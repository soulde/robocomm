from abc import ABC, abstractmethod
import json
import numpy as np
import io


def serialize(msg: dict) -> bytes:
    bio = io.BytesIO()
    np.save(bio, msg)
    return bio.getvalue()


def deserialize(msg: bytes) -> dict:
    return np.load(io.BytesIO(msg), allow_pickle=True)


if __name__ == '__main__':
    data = {
        'a': np.array([1, 2, 3]),
        'alpha': np.array([[1, 23.4, 5], [5, 6, 7, ]]),
        'b': 123,
        'c': 'ssss',
        'd': 123.,
        123: 'abc'
    }
    print(deserialize(serialize(data)))
