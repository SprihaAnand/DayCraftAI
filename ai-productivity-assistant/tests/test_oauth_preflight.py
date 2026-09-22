from __future__ import annotations

import unittest

from pages.settings import _redirect_preflight


class RedirectPreflightTests(unittest.TestCase):
    def test_matching_cloud_origin_is_ready(self) -> None:
        result = _redirect_preflight(
            "https://daycraftai.streamlit.app",
            "https://daycraftai.streamlit.app/~/+/",
        )

        self.assertTrue(result.ready)
        self.assertTrue(result.matched_current_app)

    def test_stale_cloud_origin_blocks_google_connection(self) -> None:
        result = _redirect_preflight(
            "https://daycraftsp.streamlit.app",
            "https://daycraftai.streamlit.app",
        )

        self.assertFalse(result.ready)
        self.assertFalse(result.matched_current_app)
        self.assertIn("different app address", result.message)

    def test_streamlit_dashboard_is_not_a_callback(self) -> None:
        result = _redirect_preflight("https://share.streamlit.io", None)

        self.assertFalse(result.ready)
        self.assertIsNone(result.matched_current_app)

    def test_markdown_value_is_rejected(self) -> None:
        result = _redirect_preflight("[https://daycraftai.streamlit.app](https://daycraftai.streamlit.app)", None)

        self.assertFalse(result.ready)
        self.assertIsNone(result.matched_current_app)

    def test_callback_path_is_rejected(self) -> None:
        result = _redirect_preflight(
            "https://daycraftai.streamlit.app/old-callback",
            "https://daycraftai.streamlit.app",
        )

        self.assertFalse(result.ready)
        self.assertIsNone(result.matched_current_app)

    def test_local_callback_is_valid_without_browser_context(self) -> None:
        result = _redirect_preflight("http://localhost:8501", None)

        self.assertTrue(result.ready)
        self.assertIsNone(result.matched_current_app)


if __name__ == "__main__":
    unittest.main()
