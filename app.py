import math
import os
import sqlite3
from datetime import datetime

from flask import Flask, g, render_template, request

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get(
    "BMI_DATABASE_PATH", os.path.join(app.instance_path, "bmi_history.db")
)


def get_db():
    if "db" not in g:
        database_path = app.config["DATABASE"]
        os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute(
            """
            CREATE TABLE IF NOT EXISTS bmi_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                bmi REAL NOT NULL,
                calculated_at TEXT NOT NULL
            )
            """
        )
    return g.db


@app.teardown_appcontext
def close_db(_error):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def get_users():
    return get_db().execute(
        """
        SELECT user_name, COUNT(*) AS record_count
        FROM bmi_history
        GROUP BY user_name
        ORDER BY user_name COLLATE NOCASE, user_name
        """
    ).fetchall()


def get_user_history(user_name):
    return get_db().execute(
        """
        SELECT bmi, calculated_at
        FROM bmi_history
        WHERE user_name = ?
        ORDER BY calculated_at DESC, id DESC
        """,
        (user_name,),
    ).fetchall()


def bmi_guidance(bmi):
    if bmi < 18.5:
        return {
            "label": "體重過輕",
            "tone": "low",
            "advice": "留意是否攝取足夠且均衡的營養，規律進食並搭配適度肌力活動；若體重持續下降，建議諮詢醫師或營養師。",
        }
    if bmi < 24:
        return {
            "label": "健康體位",
            "tone": "healthy",
            "advice": "維持均衡飲食與規律運動，並持續留意睡眠及生活習慣，幫助保持健康體位。",
        }
    if bmi < 27:
        return {
            "label": "體重過重",
            "tone": "high",
            "advice": "可從減少含糖飲料、增加蔬菜與日常活動量開始，循序建立適合自己的健康習慣。",
        }
    return {
        "label": "肥胖",
        "tone": "high",
        "advice": "建議與醫師或營養師討論適合自己的飲食及運動計畫，並留意血壓、血糖等健康指標。",
    }


def parse_positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


@app.route("/", methods=["GET", "POST"])
def index():
    name_input = ""
    height_input = ""
    weight_input = ""
    errors = {}
    result = None

    if request.method == "POST":
        name_input = request.form.get("name", "").strip()
        height_input = request.form.get("height", "").strip()
        weight_input = request.form.get("weight", "").strip()
        if not name_input:
            errors["name"] = "請輸入姓名。"
        elif len(name_input) > 80:
            errors["name"] = "姓名不可超過 80 個字元。"

        height = parse_positive_number(height_input)
        weight = parse_positive_number(weight_input)

        if height is None:
            errors["height"] = "請輸入大於 0 的有效身高（公分）。"
        if weight is None:
            errors["weight"] = "請輸入大於 0 的有效體重（公斤）。"

        if not errors:
            height_meters = height / 100
            height_squared = height_meters * height_meters
            if not math.isfinite(height_squared) or height_squared == 0:
                errors["height"] = "無法使用這組數值計算 BMI，請檢查身高與體重。"
            else:
                bmi = weight / height_squared
                if not math.isfinite(bmi) or bmi == 0:
                    errors["weight"] = "無法使用這組數值計算 BMI，請檢查身高與體重。"
                else:
                    displayed_bmi = round(bmi, 1)
                    result = {"bmi": f"{displayed_bmi:.1f}", **bmi_guidance(displayed_bmi)}
                    get_db().execute(
                        """
                        INSERT INTO bmi_history (user_name, bmi, calculated_at)
                        VALUES (?, ?, ?)
                        """,
                        (
                            name_input,
                            displayed_bmi,
                            datetime.now().astimezone().isoformat(timespec="seconds"),
                        ),
                    )
                    get_db().commit()

    selected_user = request.args.get("user", "").strip()
    users = get_users()
    if selected_user and not any(user["user_name"] == selected_user for user in users):
        selected_user = ""

    return render_template(
        "index.html",
        name_input=name_input,
        height_input=height_input,
        weight_input=weight_input,
        errors=errors,
        result=result,
        users=users,
        selected_user=selected_user,
        user_history=get_user_history(selected_user) if selected_user else [],
    )


if __name__ == "__main__":
    app.run(debug=True)
