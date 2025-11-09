from flask import Blueprint, render_template, request, url_for, redirect, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from link import *
from api.sql import *
from werkzeug.utils import secure_filename
from flask import current_app
from datetime import datetime

UPLOAD_FOLDER = 'static/product'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

manager = Blueprint('manager', __name__, template_folder='../templates')

def config():
    current_app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    config = current_app.config['UPLOAD_FOLDER'] 
    return config

@manager.route('/', methods=['GET', 'POST'])
@login_required
def home():
    return redirect(url_for('manager.courseManager'))

@manager.route('/courseManager', methods=['GET', 'POST'])
@login_required
def courseManager():
    if request.method == 'GET':
        if(current_user.role == 'user'):
            flash('No permission')
            return redirect(url_for('index'))
        
    if 'delete' in request.values:
        courseid = request.values.get('delete')

        # 1. 檢查 'courseschedule' 表中是否已存在此 courseId
        if CourseSchedule.check_course_in_use(courseid):
            # 如果 check_course_in_use 返回了資料 (不是 None)，表示已存在
            flash('刪除失敗：此課程已有排程，無法刪除。', 'danger')
            return redirect(url_for('manager.courseManager'))
        try:
            Course.delete_course(courseid)
            flash('課程已成功刪除', 'success')
        except Exception as e:
            # 捕捉其他可能的資料庫錯誤
            flash(f'刪除失敗：{e}', 'error')
    
    elif 'edit' in request.values:
        courseid = request.values.get('edit')
        return redirect(url_for('manager.edit', courseid = courseid))
    
    course_data = sport()
    return render_template('courseManager.html', book_data = course_data, user = current_user.name)

def sport():
    row = Course.get_all_course()
    course_data = []
    for i in row:
        sport = {
            '課程編號': i[0],
            '課程名稱': i[1],
            '教室': i[2],
            '學員人數限制': i[3]
        }
        course_data.append(sport)
    return course_data

@manager.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        data = ""
        while(data != None):
            # number = str(random.randrange( 10000, 99999))
            # en = random.choice(string.ascii_letters)
            number = str(int(Course.get_courseid()[0]) + 1).zfill(4)
            courseid = 'co' + number
            data = Course.get_course(courseid)

        coursename = request.values.get('coursename')
        classroom = request.values.get('classroom')
        qtylimit = int(request.values.get('qtylimit'))


        # 檢查是否正確獲取到所有欄位的數據
        if coursename is None or classroom is None or qtylimit is None :
            flash('所有欄位都是必填的，請確認輸入內容。')
            return redirect(url_for('manager.courseManager'))

        # 檢查欄位的長度
        if len(coursename) < 1 or len(classroom) < 1:
            flash('課程名稱或教室不可為空。')
            return redirect(url_for('manager.courseManager'))

        Course.add_course(
            {'courseid' : courseid,
             'coursename' : coursename,
             'classroom' : classroom,
             'studentlimit' : qtylimit
            }
        )

        return redirect(url_for('manager.courseManager'))

    return render_template('courseManager.html')

@manager.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        Course.update_course(
            {
                'courseid' : request.values.get('courseid'),
                'coursename' : request.values.get('coursename'),
                'classroom' : request.values.get('classroom'),
                'studentlimit' : request.values.get('qtylimit')
            }
        )
        return redirect(url_for('manager.courseManager'))
    
    if request.method == 'GET':
        if(current_user.role == 'user'):
            flash('No permission')
            return redirect(url_for('bookstore'))
        
        # 1. 從 URL 參數安全地取得 courseid
        courseid = request.args.get('courseid') 
        
        # 2. 檢查 courseid 是否存在
        if not courseid:
            flash('錯誤：未指定課程編號。')
            return redirect(url_for('manager.courseManager'))

        # 3. 將 courseid 傳遞給 show_info 函式
        course = show_info(courseid) 
        
        # 4. 檢查課程是否存在
        if not course:
            flash('錯誤：找不到該課程。')
            return redirect(url_for('manager.courseManager'))

        return render_template('edit.html', data=course)

def show_info(courseid):
    data = Course.get_course(courseid)
    # 建議增加一個檢查，以防 data 為 None
    if not data:
        return None
    coursename = data[1]
    classroom = data[2]
    qtylimit = data[3]

    course = {
        '課程編號': courseid,
        '課程名稱': coursename,
        '教室': classroom,
        '學員人數限制': qtylimit
    }
    return course


@manager.route('/courseSchedule', methods=['GET', 'POST'])
@login_required 
def courseSchedule():
    
    # --- 處理 POST 請求 (新增排程) ---
    if request.method == 'POST':
        # 權限檢查 (範例：假設 'coach' 或 'manager' 才能新增)
        if current_user.role not in ('coach', 'manager'):
             flash('No permission')
             return redirect(url_for('bookstore')) 

        try:
            # 1. 從表單接收資料 (全小寫)
            course_id = request.values.get('courseid')
            coach_id = request.values.get('coachid')
            schedule_date_str = request.values.get('scheduledate')
            time_slot = request.values.get('timeslot')

            # 2. 轉換 DDL 需要的欄位
            date_obj = datetime.strptime(schedule_date_str, '%Y-%m-%d')
            month = date_obj.month
            day_of_week = date_obj.weekday() + 1 # (1=週一, 7=週日)

            # 3. 組合資料字典 (欄位全小寫)
            schedule_data = {
                'courseid': course_id,
                'coachid': coach_id,
                'scheduledate': date_obj.date(),
                'timeslot': time_slot,
                'month': month,
                'dayofweek': day_of_week
            }
            
            # 4. 呼叫 sql.py 的方法
            CourseSchedule.create(schedule_data)
            flash('課程時段新增成功！', 'success')

        except Exception as e:
            flash(f'新增失敗：{e}', 'error') # 例如主鍵重複
            
        return redirect(url_for('manager.courseSchedule'))

    # --- 處理 GET 請求 (顯示頁面) ---
    if request.method == 'GET':
        # 權限檢查
        if current_user.role not in ('coach', 'manager'):
             flash('No permission')
             return redirect(url_for('bookstore'))

        # 1. 呼叫輔助函式來獲取格式化後的資料
        courses_list = get_all_courses_for_dropdown()
        coaches_list = get_all_coaches_for_dropdown()
        schedules_list = get_all_schedules_list()
            
        # 2. 渲染模板
        return render_template(
            'courseSchedule.html', 
            courses=courses_list, 
            coaches=coaches_list, 
            schedules=schedules_list
        )


@manager.route('/courseSchedule/delete', methods=['POST'])
@login_required 
def delete_courseSchedule():         
    try:
        # 1. 從隱藏表單欄位接收複合主鍵 (全小寫)
        course_id = request.values.get('courseid')
        schedule_date = request.values.get('scheduledate')
        time_slot = request.values.get('timeslot')
        
        # 2. 檢查 'booking' 表中是否已存在此排程
        if Booking.check_schedule_in_use(course_id, schedule_date, time_slot):
            # 如果 check_schedule_in_use 返回了資料 (不是 None)，表示已存在
            flash('刪除失敗：此排程已有會員預約，無法刪除。', 'danger')
            return redirect(url_for('manager.courseSchedule'))

        # 23. 呼叫 sql.py 的方法
        CourseSchedule.delete(course_id, schedule_date, time_slot)
        flash('課程時段已刪除')
        
    except Exception as e:
        flash(f'刪除失敗：{e}')

    return redirect(url_for('manager.courseSchedule'))


@manager.route('/plan', methods=['GET', 'POST'])
@login_required 
def plan():
    if request.method == 'POST':
        # 權限檢查 (範例：假設 'coach' 或 'manager' 才能新增)
        if current_user.role not in ('coach', 'manager'):
             flash('No permission')
             return redirect(url_for('bookstore')) 
        
        try:
            # 1. 從表單接收資料 (已移除 'planid')
            input_data = {
                'planname': request.values.get('planname'),
                'period': request.values.get('period'),
                'monthlycharge': request.values.get('monthlycharge')
            }
            
            # 2. 呼叫修改過的 sql.py 方法ㄗㄣ
            Plan.add_plan(input_data)
            flash('合約方案新增成功！', 'success')

        except Exception as e:
            flash(f'新增失敗：{e}', 'error')
            
        return redirect(url_for('manager.plan'))

    # --- 處理 GET 請求 (顯示頁面) ---
    if request.method == 'GET':
        # 權限檢查 (可選)
        if current_user.role not in ('coach', 'manager'):
             flash('No permission', 'error')
             return redirect(url_for('manager.courseManager'))

        # 1. 呼叫輔助函式來獲取格式化後的資料
        plans_list = get_all_plans_list()
            
        # 2. 渲染模板
        return render_template(
            'plan.html', 
            plans=plans_list
        )


@manager.route('/plan/delete', methods=['POST'])
@login_required 
def delete_plan():         
    try:
        plan_id = request.values.get('planid')

        # 1. 檢查 'confirm' 表中是否已存在此 planId
        if ConfirmSQL.check_plan_in_use(plan_id):
            # 如果 check_plan_in_use 返回了資料 (不是 None)，表示已存在
            flash('刪除失敗：此方案已有會員正在使用，無法刪除。', 'danger')
            return redirect(url_for('manager.plan'))
        
        # 2. 呼叫 sql.py 的方法
        Plan.delete_plan(plan_id)
        flash('合約方案已刪除', 'success')
        
    except Exception as e:
        # 捕捉錯誤，例如該方案已被會員使用 (foreign key constraint)
        flash(f'刪除失敗：{e}', 'error')

    return redirect(url_for('manager.plan'))

# ==========================================================
# 輔助函式 (View Helpers)
# (依照您的 show_info 風格，用來格式化從 sql.py 取得的資料)
# ==========================================================

def get_all_schedules_list():
    """
    獲取並格式化所有排程，用於模板
    """
    raw_data = CourseSchedule.get_all_joined() # 呼叫 sql.py 的方法
    schedules = []
    if not raw_data:
        return []
    
    for row in raw_data:
        # 索引對應 get_all_joined() 的 SELECT 順序
        schedules.append({
            'courseid': row[0],
            'scheduledate': row[1],
            'timeslot': row[2],
            'coursename': row[3],
            'cname': row[4]
        })
    return schedules

def get_all_courses_for_dropdown():
    """
    獲取並格式化所有課程，用於下拉選單
    """
    # 呼叫您 sql.py 中的 Course.get_all_course()
    raw_data = Course.get_all_course() 
    courses = []
    if not raw_data:
        return []
        
    for row in raw_data:
        # 索引對應 course 表的 SELECT *
        courses.append({
            'courseid': row[0],
            'coursename': row[1]
        })
    return courses

def get_all_coaches_for_dropdown():
    """
    獲取並格式化所有教練，用於下拉選單
    """
    # 呼叫我們剛才在 sql.py 新增的 Coach.get_all_coach()
    raw_data = Coach.get_all_coach() 
    coaches = []
    if not raw_data:
        return []

    for row in raw_data:
        # 索引對應 coach 表的 SELECT *
        coaches.append({
            'coachid': row[0],
            'cname': row[1]
        })
    return coaches

def get_all_plans_list():
    """
    獲取並格式化所有合約方案
    """
    raw_data = Plan.get_all_plan() # 呼叫 sql.py 的方法
    plans = []
    if not raw_data:
        return []
    
    for row in raw_data:
        # 索引對應 plan 表的 SELECT *
        # (planid, planname, period, monthlycharge)
        plans.append({
            'planid': row[0],
            'planname': row[1],
            'period': row[2],
            'monthlycharge': row[3] 
        })
    return plans

# ==========================================================