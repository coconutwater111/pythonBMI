import os
import tempfile
import unittest

from app import app, bmi_guidance


class BmiAppTests(unittest.TestCase):
    def setUp(self):
        self.database_directory = tempfile.TemporaryDirectory()
        old_database = app.config.get("DATABASE")
        app.config["DATABASE"] = os.path.join(self.database_directory.name, "test.sqlite")
        self.addCleanup(app.config.__setitem__, "DATABASE", old_database)
        self.addCleanup(self.database_directory.cleanup)
        self.client = app.test_client()

    def test_initial_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("了解自己的<br><em>健康狀況。</em>", page)
        self.assertIn("計算你的 BMI", page)
        self.assertIn("用戶 BMI 紀錄", page)
        self.assertIn("尚無計算紀錄", page)

    def test_calculation_and_advice(self):
        response = self.client.post("/", data={"name": "小明", "height": "170", "weight": "65"})
        page = response.get_data(as_text=True)
        self.assertIn("22.5", page)
        self.assertIn("健康體位", page)
        self.assertIn("維持均衡飲食", page)
        self.assertIn("小明", page)

    def test_user_history_shows_only_selected_users_records(self):
        for name, weight in [("小明", "65"), ("小華", "60"), ("小明", "70")]:
            self.client.post("/", data={"name": name, "height": "170", "weight": weight})

        response = self.client.get("/?user=小明")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("小明 的歷次 BMI", page)
        self.assertIn("22.5", page)
        self.assertIn("24.2", page)
        self.assertNotIn("20.8", page)
        self.assertIn("計算時間", page)
        self.assertIn("datetime=", page)

    def test_name_is_required_to_save_a_calculation(self):
        response = self.client.post("/", data={"height": "170", "weight": "65"})
        page = response.get_data(as_text=True)
        self.assertIn("請輸入姓名", page)
        self.assertNotIn("YOUR RESULT", page)

    def test_low_and_high_results_have_distinct_tones(self):
        for weight, tone, category in [
            ("18.4", "low", "體重過輕"),
            ("24", "high", "體重過重"),
        ]:
            with self.subTest(weight=weight):
                response = self.client.post("/", data={"name": "測試用戶", "height": "100", "weight": weight})
                page = response.get_data(as_text=True)
                self.assertIn(f'class="result-panel {tone}"', page)
                self.assertIn(category, page)

    def test_taiwan_adult_thresholds(self):
        for bmi, category in [
            (18.4, "體重過輕"),
            (18.5, "健康體位"),
            (23.9, "健康體位"),
            (24.0, "體重過重"),
            (26.9, "體重過重"),
            (27.0, "肥胖"),
        ]:
            with self.subTest(bmi=bmi):
                self.assertEqual(bmi_guidance(bmi)["label"], category)

    def test_invalid_fields_do_not_produce_result(self):
        for height, weight in [("", "65"), ("0", "65"), ("abc", "65"), ("170", "-2"), ("inf", "65"), ("170", "nan"), ("1e-300", "65"), ("1e308", "65"), ("1", "1e308")]:
            with self.subTest(height=height, weight=weight):
                response = self.client.post("/", data={"name": "測試用戶", "height": height, "weight": weight})
                page = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn('aria-invalid="true"', page)
                self.assertNotIn("YOUR RESULT", page)

    def test_input_is_escaped(self):
        response = self.client.post("/", data={"name": "測試用戶", "height": '<script>alert(1)</script>', "weight": "65"})
        page = response.get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("請輸入大於 0", page)


if __name__ == "__main__":
    unittest.main()
