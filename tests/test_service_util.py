import unittest

from parameterized import parameterized

from cltl.backend.api.util import bytes_per_frame


class ServiceUtilTest(unittest.TestCase):
    @parameterized.expand([
        (0, (0, 1, 1)),
        (0, (0, 1, 2)),
        (0, (0, 2, 1)),
        (0, (0, 1, 1)),
        (1, (1, 1, 1)),
        (2, (1, 2, 1)),
        (2, (1, 1, 2)),
        (4, (1, 2, 2)),
        (10, (10, 1, 1)),
        (20, (10, 2, 1)),
        (20, (10, 1, 2)),
        (40, (10, 2, 2))
    ])
    def test_bytes_per_frame(self, expected, args):
        self.assertEqual(expected, bytes_per_frame(*args), f"expected: {expected}, args: {args}")

    def test_raw_frames_to_np(self):
        pass

    def test_retrieve_from_storage(self):
        pass

