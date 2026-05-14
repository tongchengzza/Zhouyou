import unittest

from xhs_playwright import _parse_cookie


class ParseCookieTest(unittest.TestCase):
    def test_basic_three_forms(self):
        raw = "a=1; b=2; c=3"
        cookie_dict, pw_cookies, cookie_header = _parse_cookie(raw)

        self.assertEqual(cookie_dict, {"a": "1", "b": "2", "c": "3"})
        self.assertEqual(cookie_header, "a=1; b=2; c=3")
        self.assertEqual(len(pw_cookies), 3)
        self.assertEqual(
            pw_cookies[0],
            {"name": "a", "value": "1", "domain": ".xiaohongshu.com", "path": "/"},
        )

    def test_value_with_equals_sign(self):
        raw = "token=abc==; web_session=xyz"
        cookie_dict, _, _ = _parse_cookie(raw)
        self.assertEqual(cookie_dict["token"], "abc==")
        self.assertEqual(cookie_dict["web_session"], "xyz")

    def test_trailing_semicolon_and_whitespace(self):
        raw = "  a=1;  b=2;  "
        cookie_dict, _, _ = _parse_cookie(raw)
        self.assertEqual(cookie_dict, {"a": "1", "b": "2"})

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            _parse_cookie("")
        with self.assertRaises(ValueError):
            _parse_cookie("   ")


if __name__ == "__main__":
    unittest.main()
