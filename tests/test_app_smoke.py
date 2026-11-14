from __future__ import annotations

import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

APP_PATH = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


@unittest.skipUnless(STREAMLIT_AVAILABLE, "streamlit chưa được cài")
class StreamlitSmokeTest(unittest.TestCase):
    def test_persona_assess_and_plan(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 3)

        app.button(key="assess").click().run()
        self.assertFalse(app.exception)
        self.assertIn("assessment", app.session_state)

        app.button(key="run_plan").click().run()
        self.assertFalse(app.exception)
        self.assertIn("plan", app.session_state)
        plan = app.session_state["plan"]
        self.assertEqual(plan["budget"], 12)
        self.assertIn(plan["result"]["status"], {"optimal", "best_effort"})


if __name__ == "__main__":
    unittest.main()
