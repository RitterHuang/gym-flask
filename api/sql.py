import os
from typing import Optional, Sequence, Any
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# ------------------------------------------------------------
# 讀取 .env（在本機用），Render 上則用 Environment 裡的變數
# ------------------------------------------------------------
load_dotenv()

DB_USER = os.getenv("DB_USER", "project_7")
DB_PASSWORD = os.getenv("DB_PASSWORD", "i68g8q")
DB_NAME = os.getenv("DB_NAME", "project_7")
DB_HOST = os.getenv("DB_HOST", "140.117.68.66")
DB_PORT = os.getenv("DB_PORT", "5432")

# 全域連線池（lazy 建立）
_DB_POOL: Optional[pool.SimpleConnectionPool] = None


def _get_pool() -> pool.SimpleConnectionPool:
    """
    第一次呼叫時建立連線池，之後重複使用。
    """
    global _DB_POOL
    if _DB_POOL is None:
        dsn = {
            "user": DB_USER,
            "password": DB_PASSWORD,
            "host": DB_HOST,
            "port": DB_PORT,
            "dbname": DB_NAME,
        }
        # 你可以依需求調整 maxconn
        _DB_POOL = pool.SimpleConnectionPool(1, 20, **dsn)
    return _DB_POOL


class DB:
    @staticmethod
    def connect():
        return _get_pool().getconn()

    @staticmethod
    def release(connection):
        _get_pool().putconn(connection)

    @staticmethod
    def execute_input(sql: str, input_params: Sequence[Any]):
        """
        有參數、會寫入/更新資料的指令，用這個（會 commit）
        """
        if not isinstance(input_params, (tuple, list)):
            raise TypeError(
                f"Input should be a tuple or list, got: {type(input_params).__name__}"
            )

        connection = DB.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, input_params)
                connection.commit()
        except psycopg2.Error as e:
            print(f"Error executing SQL: {e}")
            connection.rollback()
            raise e
        finally:
            DB.release(connection)

    @staticmethod
    def execute(sql: str, input_params: Optional[Sequence[Any]] = None):
        """
        不需要回傳結果，只要執行（也會 commit）
        """
        connection = DB.connect()
        try:
            with connection.cursor() as cursor:
                if input_params is None:
                    cursor.execute(sql)
                else:
                    cursor.execute(sql, input_params)
                connection.commit()
        except psycopg2.Error as e:
            print(f"Error executing SQL: {e}")
            connection.rollback()
            raise e
        finally:
            DB.release(connection)

    @staticmethod
    def fetchall(sql: str, input_params: Optional[Sequence[Any]] = None):
        """
        回傳多筆資料
        """
        connection = DB.connect()
        try:
            with connection.cursor() as cursor:
                if input_params is None:
                    cursor.execute(sql)
                else:
                    cursor.execute(sql, input_params)
                return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Error fetching data: {e}")
            raise e
        finally:
            DB.release(connection)

    @staticmethod
    def fetchone(sql: str, input_params: Optional[Sequence[Any]] = None):
        """
        回傳一筆資料
        """
        connection = DB.connect()
        try:
            with connection.cursor() as cursor:
                if input_params is None:
                    cursor.execute(sql)
                else:
                    cursor.execute(sql, input_params)
                return cursor.fetchone()
        except psycopg2.Error as e:
            print(f"Error fetching data: {e}")
            raise e
        finally:
            DB.release(connection)


# ==================== 以下是你原本的各種 Model ====================

class Member:
    @staticmethod
    def get_by_id(memberId):
        sql = "SELECT mname, password, status FROM sportMember WHERE memberId = %s"
        return DB.fetchall(sql, (memberId,))

    @staticmethod
    def create_member(input_data):
        sql = (
            "INSERT INTO sportMember("
            "memberId, mName, birthDate, gender, phoneNumber, password, registerdate, status"
            ") VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)"
        )
        DB.execute_input(
            sql,
            (
                input_data["memberId"],
                input_data["mName"],
                input_data["birthDate"],
                input_data["gender"],
                input_data["phoneNumber"],
                input_data["password"],
                "無合約",
            ),
        )

    @staticmethod
    def update_status_by_id(memberId, new_status):
        """
        會員簽署合約後，更新其狀態。
        """
        sql = "UPDATE sportMember SET Status = %s WHERE MemberID = %s"
        return DB.execute_input(sql, (new_status, memberId))


class Coach:
    @staticmethod
    def get_by_id(coachId):
        sql = "SELECT cname, password FROM Coach WHERE coachId = %s"
        return DB.fetchall(sql, (coachId,))

    @staticmethod
    def create_coach(input_data):
        sql = "INSERT INTO coach(coachId, cName, coachingType, password) VALUES (%s, %s, %s, %s)"
        DB.execute_input(
            sql,
            (
                input_data["coachId"],
                input_data["cName"],
                input_data["coachingType"],
                input_data["password"],
            ),
        )

    @staticmethod
    def get_all_coach():
        """
        查詢所有教練 (用於下拉選單)
        """
        sql = "SELECT * FROM coach ORDER BY cname"
        return DB.fetchall(sql)


class Plan:
    @staticmethod
    def get_next_planid():
        """
        計算下一個 planid (格式為 'p' + 4位數字，例如 p0001)
        """
        sql = """
            SELECT MAX(CAST(SUBSTRING(planid FROM 2) AS INT)) 
            FROM plan 
            WHERE planid LIKE 'p%'
        """
        result = DB.fetchone(sql)

        if result and result[0] is not None:
            next_num = result[0] + 1
        else:
            next_num = 1

        next_id = f"p{str(next_num).zfill(4)}"
        return next_id

    @staticmethod
    def get_all_plan():
        """
        查詢所有合約方案
        """
        sql = "SELECT * FROM plan ORDER BY planid"
        return DB.fetchall(sql)

    @staticmethod
    def get_period_by_id(planId):
        """
        根據 PlanID 獲取方案的 'period' (週期，單位：月)
        """
        sql = "SELECT period FROM plan WHERE planid = %s"
        return DB.fetchone(sql, (planId,))

    @staticmethod
    def add_plan(input_data):
        """
        自動產生 planid 並新增合約方案
        input_data 字典現在只需要 'planname', 'period', 'monthlycharge'
        """
        new_planid = Plan.get_next_planid()

        sql = """
            INSERT INTO plan (planid, planname, period, monthlycharge) 
            VALUES (%s, %s, %s, %s)
        """
        DB.execute_input(
            sql,
            (
                new_planid,
                input_data["planname"],
                input_data["period"],
                input_data["monthlycharge"],
            ),
        )

    @staticmethod
    def delete_plan(planid):
        """
        根據 planId 刪除一筆合約方案
        """
        sql = "DELETE FROM plan WHERE planid = %s"
        DB.execute_input(sql, (planid,))


class Course:
    @staticmethod
    def count():
        sql = "SELECT COUNT(*) FROM course"
        return DB.fetchone(sql)

    @staticmethod
    def get_course(courseid):
        sql = "SELECT * FROM course WHERE courseid = %s"
        return DB.fetchone(sql, (courseid,))

    @staticmethod
    def get_all_course():
        sql = "SELECT * FROM course"
        return DB.fetchall(sql)

    @staticmethod
    def get_name(courseid):
        sql = "SELECT coursename FROM course WHERE courseid = %s"
        return DB.fetchone(sql, (courseid,))[0]

    @staticmethod
    def add_course(input_data):
        sql = (
            "INSERT INTO course (courseid, coursename, classroom, studentlimit) "
            "VALUES (%s, %s, %s, %s)"
        )
        DB.execute_input(
            sql,
            (
                input_data["courseid"],
                input_data["coursename"],
                input_data["classroom"],
                input_data["studentlimit"],
            ),
        )

    @staticmethod
    def delete_course(courseid):
        sql = "DELETE FROM course WHERE courseid = %s"
        DB.execute_input(sql, (courseid,))

    @staticmethod
    def update_course(input_data):
        sql = (
            "UPDATE course SET coursename = %s, classroom = %s, studentlimit = %s "
            "WHERE courseid = %s"
        )
        DB.execute_input(
            sql,
            (
                input_data["coursename"],
                input_data["classroom"],
                input_data["studentlimit"],
                input_data["courseid"],
            ),
        )

    @staticmethod
    def get_courseid():
        sql = "SELECT RIGHT(MAX(courseid), 4) FROM course"
        return DB.fetchone(sql)


class CourseSchedule:
    @staticmethod
    def create(input_data):
        """
        新增一筆課程時段紀錄
        """
        sql = (
            "INSERT INTO courseschedule "
            "(courseid, coachid, scheduledate, timeslot, month, dayofweek) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        DB.execute_input(
            sql,
            (
                input_data["courseid"],
                input_data["coachid"],
                input_data["scheduledate"],
                input_data["timeslot"],
                input_data["month"],
                input_data["dayofweek"],
            ),
        )

    @staticmethod
    def delete(courseid, scheduledate, timeslot):
        """
        根據複合主鍵刪除一筆課程時段
        """
        sql = (
            "DELETE FROM courseschedule "
            "WHERE courseid = %s AND scheduledate = %s AND timeslot = %s"
        )
        DB.execute_input(sql, (courseid, scheduledate, timeslot))

    @staticmethod
    def get_all_joined():
        """
        查詢所有已排定的時段，並 JOIN 課程與教練名稱
        """
        sql = """
            SELECT 
                cs.courseid, cs.scheduledate, cs.timeslot,
                c.coursename, 
                co.cname
            FROM 
                courseschedule cs
            JOIN 
                course c ON cs.courseid = c.courseid
            JOIN 
                coach co ON cs.coachid = co.coachid
            ORDER BY 
                cs.scheduledate DESC, cs.timeslot
        """
        return DB.fetchall(sql)

    @staticmethod
    def get_schedules_by_week(start_date, end_date):
        """
        獲取特定日期範圍內的所有排程，並 JOIN 課程、教練名稱、人數限制
        """
        sql = """
            SELECT 
                cs.courseid, 
                cs.scheduledate, 
                cs.timeslot, 
                cs.coachid, 
                c.coursename, 
                co.cname,
                c.studentlimit 
            FROM courseschedule cs
            JOIN course c ON cs.courseid = c.courseid
            JOIN coach co ON cs.coachid = co.coachid
            WHERE cs.scheduledate BETWEEN %s AND %s
            ORDER BY cs.scheduledate, cs.timeslot;
        """
        return DB.fetchall(sql, (start_date, end_date))

    @staticmethod
    def check_course_in_use(courseid):
        """
        檢查是否有任何排程 (CourseSchedule) 正在使用此 courseid。
        """
        sql = "SELECT 1 FROM courseschedule WHERE courseid = %s LIMIT 1"
        return DB.fetchone(sql, (courseid,))


class Booking:
    """
    管理與 Booking (預約) 相關的 SQL 查詢
    """

    @staticmethod
    def get_bookings_by_member(memberId):
        """
        查詢特定會員的所有預約紀錄 (未來的)，並 JOIN 課程資訊
        """
        sql = """
            SELECT 
                b.courseid, 
                b.scheduledate, 
                b.timeslot, 
                c.coursename, 
                co.cname
            FROM booking b
            JOIN courseschedule cs ON b.courseid = cs.courseid 
                                  AND b.scheduledate = cs.scheduledate 
                                  AND b.timeslot = cs.timeslot
            JOIN course c ON b.courseid = c.courseid
            JOIN coach co ON cs.coachid = co.coachid
            WHERE b.memberid = %s AND b.scheduledate >= CURRENT_DATE
            ORDER BY b.scheduledate ASC, b.timeslot ASC;
        """
        return DB.fetchall(sql, (memberId,))

    @staticmethod
    def check_booking_exists(courseId, scheduleDate, timeSlot, memberId):
        """
        檢查會員是否已預約該時段
        """
        sql = """
            SELECT 1 FROM booking
            WHERE courseid = %s AND scheduledate = %s AND timeslot = %s AND memberid = %s;
        """
        return DB.fetchone(sql, (courseId, scheduleDate, timeSlot, memberId))

    @staticmethod
    def count_bookings_for_schedule(courseId, scheduleDate, timeSlot):
        """
        計算某個特定課程時段的總預約人數
        """
        sql = """
            SELECT COUNT(*) FROM booking
            WHERE courseid = %s AND scheduledate = %s AND timeslot = %s;
        """
        return DB.fetchone(sql, (courseId, scheduleDate, timeSlot))

    @staticmethod
    def create_booking(courseId, scheduleDate, timeSlot, memberId):
        """
        新增一筆預約紀錄
        """
        sql = """
            INSERT INTO booking (courseid, scheduledate, timeslot, memberid)
            VALUES (%s, %s, %s, %s);
        """
        return DB.execute_input(sql, (courseId, scheduleDate, timeSlot, memberId))

    @staticmethod
    def delete_booking(courseId, scheduleDate, timeSlot, memberId):
        """
        刪除一筆預約紀錄
        """
        sql = """
            DELETE FROM booking
            WHERE courseid = %s AND scheduledate = %s AND timeslot = %s AND memberid = %s;
        """
        return DB.execute_input(sql, (courseId, scheduleDate, timeSlot, memberId))

    @staticmethod
    def check_schedule_in_use(courseid, scheduledate, timeslot):
        """
        檢查是否有任何會員 (Booking) 預約此 (courseid, scheduledate, timeslot)。
        """
        sql = (
            "SELECT 1 FROM booking "
            "WHERE courseid = %s AND scheduledate = %s AND timeslot = %s LIMIT 1"
        )
        return DB.fetchone(sql, (courseid, scheduledate, timeslot))


class ConfirmSQL:
    """
    管理與 Confirm (合約確認) 資料表相關的 SQL 查詢
    """

    @staticmethod
    def create_confirmation(memberId, planId, paymentType, period_months):
        """
        在 Confirm 表中新增一筆紀錄。
        startDate 設為 NOW()。
        endDate 設為 NOW() + 'X months'。
        """
        sql = """
            INSERT INTO Confirm (planId, memberId, startDate, endDate, paymentType)
            VALUES (%s, %s, NOW(), NOW() + (%s * INTERVAL '1 month'), %s)
        """
        params = (planId, memberId, period_months, paymentType)
        return DB.execute_input(sql, params)

    @staticmethod
    def check_plan_in_use(planId):
        """
        檢查是否有任何會員正在使用此 planId。
        """
        sql = "SELECT 1 FROM confirm WHERE planid = %s LIMIT 1"
        return DB.fetchone(sql, (planId,))


class Analysis:
    @staticmethod
    def month_price(i):
        sql = (
            "SELECT EXTRACT(MONTH FROM ordertime), SUM(price) "
            "FROM order_list "
            "WHERE EXTRACT(MONTH FROM ordertime) = %s "
            "GROUP BY EXTRACT(MONTH FROM ordertime)"
        )
        return DB.fetchall(sql, (i,))

    @staticmethod
    def month_count(i):
        sql = (
            "SELECT EXTRACT(MONTH FROM ordertime), COUNT(oid) "
            "FROM order_list "
            "WHERE EXTRACT(MONTH FROM ordertime) = %s "
            "GROUP BY EXTRACT(MONTH FROM ordertime)"
        )
        return DB.fetchall(sql, (i,))

    @staticmethod
    def category_sale():
        sql = (
            "SELECT SUM(total), category "
            "FROM product, record "
            "WHERE product.pid = record.pid "
            "GROUP BY category"
        )
        return DB.fetchall(sql)

    @staticmethod
    def member_sale():
        sql = (
            "SELECT SUM(price), member.mid, member.name "
            "FROM order_list, member "
            "WHERE order_list.mid = member.mid AND member.identity = %s "
            "GROUP BY member.mid, member.name "
            "ORDER BY SUM(price) DESC"
        )
        return DB.fetchall(sql, ("user",))

    @staticmethod
    def member_sale_count():
        sql = (
            "SELECT COUNT(*), member.mid, member.name "
            "FROM order_list, member "
            "WHERE order_list.mid = member.mid AND member.identity = %s "
            "GROUP BY member.mid, member.name "
            "ORDER BY COUNT(*) DESC"
        )
        return DB.fetchall(sql, ("user",))
