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
        app = AppTest.from_file(str(APP_PATH), default_timeout=120).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 4)

        app.button(key="assess").click().run()
        self.assertFalse(app.exception)
        self.assertIn("assessment", app.session_state)

        app.button(key="run_plan").click().run()
        self.assertFalse(app.exception)
        self.assertIn("plan_results", app.session_state)
        plans = app.session_state["plan_results"]
        self.assertEqual([plan["budget"] for plan in plans], [12, 15, 18])
        for plan in plans:
            self.assertIn(
                plan["result"]["status"],
                {"optimal", "best_effort", "infeasible_data_error"},
            )

    def test_s003_plan_is_best_effort_not_safe(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120).run()
        app.selectbox(key="persona_id").select("S003").run()
        app.button(key="assess").click().run()
        app.button(key="run_plan").click().run()
        self.assertFalse(app.exception)
        plans = app.session_state["plan_results"]
        for plan in plans:
            result = plan["result"]
            self.assertEqual(result["status"], "best_effort")
            self.assertTrue(result["risk_cap_exceeded"])
            self.assertGreater(
                result["expected_failed_courses"], result["expected_fail_cap"]
            )
        errors = [element.value for element in app.error]
        self.assertTrue(
            any("KHÔNG phải phương án an toàn" in message for message in errors)
        )


if __name__ == "__main__":
    unittest.main()
