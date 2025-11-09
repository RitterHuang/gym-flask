import os
import psycopg2
from dotenv import load_dotenv

from flask import (
    render_template,
    Blueprint,
    redirect,
    request,
    url_for,
    flash,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

# ============================================================
# 資料庫連線設定：環境變數優先，沒有就用老師給的那組
# ============================================================

load_dotenv()

DB_USER = os.getenv("DB_USER", "project_7")
DB_PASSWORD = os.getenv("DB_PASSWORD", "i68g8q")
DB_NAME = os.getenv("DB_NAME", "project_7")
DB_HOST = os.getenv("DB_HOST", "140.117.68.66")
DB_PORT = os.getenv("DB_PORT", "5432")


def get_connection():
    """
    每次需要時建立一個新的連線（避免長時間連線被 Render 砍掉）。
    """
    conn = psycopg2.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
    )
    conn.autocommit = True
    return conn


# ============================================================
# Flask Blueprint & LoginManager 設定
# ============================================================

api = Blueprint("api", __name__, template_folder="./templates")

# 這裡只建立 LoginManager 物件，真正綁到 app 是在 app.py 裡的 login_manager.init_app(app)
login_manager = LoginManager()
login_manager.login_view = "api.login"
login_manager.login_message = "請先登入"


class User(UserMixin):
    """
    flask_login 使用的使用者物件
    多加兩個屬性：role, name
    """

    def __init__(self):
        super().__init__()
        self.role = None  # 'member' or 'coach'
        self.name = None  # 顯示名字


# ------------------------------------------------------------
# 工具函式：從 DB 查詢會員 / 教練
# ------------------------------------------------------------

def get_member_by_account(account_id):
    """
    依照「會員登入帳號」查詢會員。

    假設 member table 結構：
      mid, fname, account, password, identity, lname

    回傳 (name, password) 或 None
    """
    sql = """
        SELECT "fname", "password"
        FROM member
        WHERE "account" = %s
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (account_id,))
            row = cur.fetchone()
            if row:
                return row[0], row[1]  # name, password
    finally:
        conn.close()
    return None


def get_coach_by_id(coach_id):
    """
    依照教練代碼查詢教練。

    假設 coach table 結構：
      coachid, cname, coachingtype, password, class

    回傳 (name, password) 或 None
    """
    sql = """
        SELECT "cname", "password"
        FROM coach
        WHERE "coachid" = %s
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (coach_id,))
            row = cur.fetchone()
            if row:
                return row[0], row[1]  # name, password
    finally:
        conn.close()
    return None


# ------------------------------------------------------------
# flask_login user_loader
# user.id 會長這樣：'member_<帳號>' 或 'coach_<教練代碼>'
# ------------------------------------------------------------

@login_manager.user_loader
def user_loader(userid: str):
    user = User()
    user.id = userid

    try:
        role, real_id = userid.split("_", 1)

        if role == "member":
            data = get_member_by_account(real_id)
            if data:
                user.role = "member"
                user.name = data[0]

        elif role == "coach":
            data = get_coach_by_id(real_id)
            if data:
                user.role = "coach"
                user.name = data[0]

    except Exception as e:
        print(f"user_loader 錯誤: {e}")

    return user


# ============================================================
# Login
# ============================================================

@api.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        account_id = request.form["account"]  # 對 member 是 account, 對 coach 是 coachid
        password = request.form["password"]

        # 1️⃣ 先試著當成會員帳號 (member.account)
        member_data = get_member_by_account(account_id)
        if member_data:
            name, db_password = member_data
            if db_password == password:
                user = User()
                user.id = f"member_{account_id}"
                user.role = "member"
                user.name = name
                login_user(user)
                # 登入成功，導向會員前台
                return redirect(url_for("frontdesk.member_home"))
            else:
                flash("*密碼錯誤")
                return redirect(url_for("api.login"))

        # 2️⃣ 如果不是會員，就試著當成教練代碼 (coach.coachid)
        coach_data = get_coach_by_id(account_id)
        if coach_data:
            name, db_password = coach_data
            if db_password == password:
                user = User()
                user.id = f"coach_{account_id}"
                user.role = "coach"
                user.name = name
                login_user(user)
                # 登入成功，導向教練後台
                return redirect(url_for("manager.courseManager"))
            else:
                flash("*密碼錯誤")
                return redirect(url_for("api.login"))

        # 3️⃣ 兩邊都找不到
        flash("*查無此帳號")
        return redirect(url_for("api.login"))

    # GET：顯示登入頁
    return render_template("login.html")


# ============================================================
# Register（如果專題有用到註冊就留著，沒用可以不呼叫）
# ============================================================

@api.route("/register", methods=["POST", "GET"])
def register():
    """
    identity: 'member' 或 'coach'
    member: 會寫入 member table
    coach : 會寫入 coach table
    """
    if request.method == "POST":
        identity = request.form["identity"]
        password = request.form["password"]

        try:
            if identity == "member":
                # 假設前端欄位：
                #   userId  -> 帳號 (member.account)
                #   fname   -> 名
                #   lname   -> 姓 (可選)
                account = request.form["userId"]
                fname = request.form.get("fname", "")
                lname = request.form.get("lname", "")

                # 檢查是否已存在
                conn = get_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT 1 FROM member WHERE "account" = %s',
                        (account,),
                    )
                    if cur.fetchone():
                        flash("此會員帳號已被註冊")
                        conn.close()
                        return redirect(url_for("api.register"))

                    cur.execute(
                        """
                        INSERT INTO member("fname", "lname", "account", "password", "identity")
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (fname, lname, account, password, "member"),
                    )
                conn.close()
                flash("會員註冊成功！請登入")

            elif identity == "coach":
                # 假設前端欄位：
                #   userId        -> 教練代碼 (coach.coachid)
                #   cName         -> 教練姓名 (coach.cname)
                #   coachingType  -> 教學類型 (coach.coachingtype)
                coach_id = request.form["userId"]
                c_name = request.form["cName"]
                coaching_type = request.form["coachingType"]

                conn = get_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT 1 FROM coach WHERE "coachid" = %s',
                        (coach_id,),
                    )
                    if cur.fetchone():
                        flash("此教練代碼已被註冊")
                        conn.close()
                        return redirect(url_for("api.register"))

                    cur.execute(
                        """
                        INSERT INTO coach("coachid", "cname", "coachingtype", "password")
                        VALUES (%s, %s, %s, %s)
                        """,
                        (coach_id, c_name, coaching_type, password),
                    )
                conn.close()
                flash("教練註冊成功！請登入")

            else:
                flash("無效的身分")
                return redirect(url_for("api.register"))

            # 成功之後導回登入頁
            return redirect(url_for("api.login"))

        except Exception as e:
            flash(f"註冊失敗: {e}")
            return redirect(url_for("api.register"))

    # GET：顯示註冊頁
    return render_template("register.html")


# ============================================================
# Logout
# ============================================================

@api.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
