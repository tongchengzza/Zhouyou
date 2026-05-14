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


class FormatTest(unittest.TestCase):
    def test_extracts_fields_from_api_response(self):
        from xhs_playwright import _format

        api_response = {
            "items": [
                {
                    "id": "abc123",
                    "note_card": {
                        "display_title": "低智商犯罪 VIP 更新日历",
                        "user": {"nickname": "追剧博主小红"},
                        "interact_info": {"liked_count": "1.2万"},
                    },
                },
                {
                    "note_id": "def456",
                    "title": "fallback 标题字段",
                    "user": {"nickname": "另一个博主"},
                    "interact_info": {"liked_count": "234"},
                },
            ]
        }
        rows = _format(api_response)
        self.assertEqual(len(rows), 2)

        self.assertEqual(rows[0]["title"], "低智商犯罪 VIP 更新日历")
        self.assertEqual(rows[0]["author"], "追剧博主小红")
        self.assertEqual(rows[0]["likes"], "1.2万")
        self.assertEqual(rows[0]["url"], "https://www.xiaohongshu.com/explore/abc123")

        self.assertEqual(rows[1]["title"], "fallback 标题字段")
        self.assertEqual(rows[1]["url"], "https://www.xiaohongshu.com/explore/def456")

    def test_empty_items(self):
        from xhs_playwright import _format
        self.assertEqual(_format({"items": []}), [])
        self.assertEqual(_format({}), [])
        self.assertEqual(_format(None), [])

    def test_missing_optional_fields(self):
        from xhs_playwright import _format
        api_response = {"items": [{"id": "x", "note_card": {}}]}
        rows = _format(api_response)
        self.assertEqual(rows[0]["title"], "（无标题）")
        self.assertEqual(rows[0]["author"], "未知")
        self.assertEqual(rows[0]["likes"], "?")


if __name__ == "__main__":
    unittest.main()
