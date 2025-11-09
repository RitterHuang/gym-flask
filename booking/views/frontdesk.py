# \booking\views\frontdesk.py

from datetime import date, timedelta, datetime
from flask import Blueprint, render_template, request, url_for, redirect, flash
from flask_login import login_required, current_user
import logging 
from link import *
from api.sql import *

# 仿照 manager.py 建立 Blueprint，變數名稱改為 'frontdesk'
frontdesk = Blueprint('frontdesk', 
                      __name__, 
                      url_prefix='/member', 
                      template_folder='../templates')


@frontdesk.route('/', methods=['GET']) # <-- 使用 @frontdesk
@login_required
def member_home():
    """
    會員登入後的儀表板/首頁。
    """
    
    if current_user.role in ('manager', 'coach'):
        flash('管理者/教練帳號，將導向至後台。', 'info')
        return redirect(url_for('manager.home')) 

    member_id = current_user.id.split('_', 1)[1]  # 去掉 'member_' 前綴取得純 ID

    try:
        member_data = Member.get_by_id(member_id)

        if not member_data:
            logging.warning(f"找不到 MemberID: {member_id} 的資料")
            flash('找不到您的會員資料，請重新登入', 'danger')
            return redirect(url_for('api.login')) 

        member_tuple = member_data[0]
        member_status = member_tuple[2] # 索引 2 是 'Status'

        if member_status == '無合約':
            logging.info(f"會員 {member_id} 狀態為 '無合約', 導向 planconfirm.html")

            plan_list = []
            try:
                all_plans_raw = Plan.get_all_plan() 
                for p in all_plans_raw:
                    plan_list.append({
                        'id': p[0],
                        'name': p[1],
                        'period': p[2],
                        'charge': p[3]
                    })
            except Exception as e:
                logging.error(f"無法載入合約方案: {e}")
                flash('無法載入合約方案列表，請聯繫客服', 'danger')

            return render_template('planconfirm.html', 
                                   user=current_user, 
                                   available_plans=plan_list)
        
        elif member_status == '有合約':
            logging.info(f"會員 {member_id} 狀態為 '有合約', 導向 booking.html")
            
            try:
                today = date.today()
                now = datetime.now()
                
                # --- 日期導覽邏輯 ---
                week_start_str = request.args.get('week_start')
                if week_start_str:
                    week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
                else:
                    # 預設為本週 (週一為 0, 週日為 6)
                    week_start = today - timedelta(days=today.weekday())
                
                week_end = week_start + timedelta(days=6)
                prev_week = (week_start - timedelta(days=7)).isoformat()
                next_week = (week_start + timedelta(days=7)).isoformat()

                # 計算本週第一天
                current_week_start_date = today - timedelta(days=today.weekday())
                
                # 產生 7 天的日期物件列表，用於表頭
                week_dates = [week_start + timedelta(days=i) for i in range(7)]

                # --- 獲取 [課程日曆] 資料 ---
                schedules_raw = CourseSchedule.get_schedules_by_week(week_start, week_end)
                
                # --- 獲取 [我的課程] 資料 ---
                my_bookings_raw = Booking.get_bookings_by_member(member_id)
                
                # 建立一個 Set (集合) 以便快速查找: (courseId, date, timeSlot)
                my_booked_set = set( (b[0], b[1], b[2]) for b in my_bookings_raw )

                # --- 資料重組：將課程資料填入 [時段][日期] 的網格中 ---
                time_slots = sorted(list(set(s[2] for s in schedules_raw))) # 獲取所有不重複的時段
                calendar_grid = {slot: {day: None for day in week_dates} for slot in time_slots}
                
                for s in schedules_raw:
                    # 索引對應 get_schedules_by_week 的 SELECT
                    # (courseid, scheduledate, timeslot, coachid, coursename, cname, studentlimit)
                    course_id, date_obj, time_slot, coach_id, course_name, coach_name, student_limit = s
                    
                    # 檢查是否已被該會員預約
                    is_booked_by_me = (course_id, date_obj, time_slot) in my_booked_set
                    
                    # 檢查是否已額滿
                    current_count = Booking.count_bookings_for_schedule(course_id, date_obj, time_slot)[0]
                    is_full = (current_count >= student_limit)

                    # 檢查時段是否已過
                    is_in_past = False
                    if date_obj < today:
                        is_in_past = True

                    elif date_obj == today:
                        try:
                            # 取得時段的開始時間 (例如 "07:15-08:15" -> "07:15")
                            course_start_time_str = time_slot.split('-')[0]
                            # 結合 '今天' 和 '課程開始時間'
                            course_start_datetime = datetime.combine(today, datetime.strptime(course_start_time_str, '%H:%M').time())
                            
                            # 如果 '現在' 晚於 '課程開始時間'
                            if now > course_start_datetime:
                                is_in_past = True
                        except Exception as time_e:
                            logging.warning(f"解析時段格式錯誤 '{time_slot}': {time_e}")

                    if time_slot in calendar_grid and date_obj in calendar_grid[time_slot]:
                        calendar_grid[time_slot][date_obj] = {
                            'courseId': course_id,
                            'date': date_obj,
                            'timeSlot': time_slot,
                            'courseName': course_name,
                            'coachName': coach_name,
                            'is_booked_by_me': is_booked_by_me,
                            'is_full': is_full,
                            'current_count': current_count,
                            'limit': student_limit,
                            'is_in_past': is_in_past
                        }
                
                # --- 格式化 [我的課程] 資料 (用於模板) ---
                my_bookings_list = []
                for b in my_bookings_raw:
                     my_bookings_list.append({
                        'courseId': b[0],
                        'scheduleDate': b[1],
                        'timeSlot': b[2],
                        'courseName': b[3],
                        'coachName': b[4]
                    })

                return render_template(
                    'booking.html', 
                    user=current_user,
                    today=today,
                    week_dates=week_dates,
                    time_slots=time_slots,
                    calendar_grid=calendar_grid,
                    my_bookings=my_bookings_list,
                    prev_week=prev_week,
                    next_week=next_week,
                    current_week_start=week_start.isoformat(), # 用於預約/取消後跳轉
                    current_week_start_date=current_week_start_date
                )

            except Exception as e:
                logging.error(f"載入預約頁面失敗: {e}")
                flash('載入預約頁面時發生錯誤', 'danger')
                return redirect(url_for('api.login'))
            
        else:
            logging.warning(f"會員 {member_id} 狀態為 '{member_status}', 拒絕存取")
            flash(f'您的帳戶狀態為「{member_status}」，目前無法預約課程。請聯繫客服。', 'danger')
            return redirect(url_for('api.login')) 

    except Exception as e:
        logging.error(f"會員儀表板載入失敗 (ID: {member_id}): {e}")
        flash('系統發生錯誤，請稍後再試', 'danger')
        return redirect(url_for('api.login'))


@frontdesk.route('/select_plan', methods=['POST']) 
@login_required
def select_plan():
    """
    處理會員選擇方案的 POST 請求
    """
    # 1. 從表單獲取數據
    selected_plan_id = request.form.get('planid')
    payment_type = request.form.get('paymentType')

    # 2. 驗證數據
    if not selected_plan_id:
        flash('您必須選擇一個合約方案', 'warning')
        return redirect(url_for('frontdesk.member_home'))
    if not payment_type:
        flash('您必須選擇一個付款方式', 'warning')
        return redirect(url_for('frontdesk.member_home'))
        
    # 3. 執行資料庫更新
    try:
        member_id = current_user.id.split('_', 1)[1]
        new_status = '有合約'

        # 步驟 3a: 獲取方案週期 (月)
        period_data = Plan.get_period_by_id(selected_plan_id)
        if not period_data:
            flash('選擇的方案無效，請重新選擇', 'danger')
            return redirect(url_for('frontdesk.member_home'))
        period_months = period_data[0] # (例如 12)

        # 步驟 3b: 在 Confirm 表中建立紀錄
        ConfirmSQL.create_confirmation(member_id, selected_plan_id, payment_type, period_months)
        
        # 步驟 3c: 更新 sportMember 的狀態
        Member.update_status_by_id(member_id, new_status)
        
        flash('方案選擇成功！歡迎開始您的健身之旅。', 'success')
        
    except Exception as e:
        logging.error(f"更新會員 {current_user.id} 合約方案失敗: {e}")
        flash('合約簽署失敗，請聯繫客服', 'danger')
    
    # 4. 導向回會員首頁
    return redirect(url_for('frontdesk.member_home'))


@frontdesk.route('/book', methods=['POST'])
@login_required
def book_course():
    """ 處理課程預約動作 """
    week_start = request.form.get('week_start') # 用於跳轉
    try:
        member_id = current_user.id.split('_', 1)[1]
        courseId = request.form.get('courseId')
        scheduleDate = request.form.get('scheduleDate')
        timeSlot = request.form.get('timeSlot')

        # --- 驗證 ---
        # 1. 檢查是否已預約
        if Booking.check_booking_exists(courseId, scheduleDate, timeSlot, member_id):
            flash('您已預約過此時段', 'warning')
            return redirect(url_for('frontdesk.member_home', week_start=week_start))

        # 2. 檢查是否額滿
        # (使用 sql.py 的 get_course，索引 [3] 是 studentlimit)
        limit = Course.get_course(courseId)[3] 
        current_count = Booking.count_bookings_for_schedule(courseId, scheduleDate, timeSlot)[0]
        
        if current_count >= limit:
            flash('此課程時段已額滿', 'danger')
            return redirect(url_for('frontdesk.member_home', week_start=week_start))
        
        # 3. 執行預約
        Booking.create_booking(courseId, scheduleDate, timeSlot, member_id)
        flash('預約成功！', 'success')

    except Exception as e:
        logging.error(f"預約失敗: {e}")
        flash('預約時發生錯誤', 'danger')
        
    return redirect(url_for('frontdesk.member_home', week_start=week_start))


@frontdesk.route('/cancel', methods=['POST'])
@login_required
def cancel_booking():
    """ 處理取消預約動作 """
    week_start = request.args.get('week_start') # 如果從日曆取消，需要 week_start
    try:
        member_id = current_user.id.split('_', 1)[1]
        courseId = request.form.get('courseId')
        scheduleDate = request.form.get('scheduleDate')
        timeSlot = request.form.get('timeSlot')

        Booking.delete_booking(courseId, scheduleDate, timeSlot, member_id)
        flash('已取消預約', 'success')

    except Exception as e:
        logging.error(f"取消預約失敗: {e}")
        flash('取消時發生錯誤', 'danger')

    if week_start:
        return redirect(url_for('frontdesk.member_home', week_start=week_start))
    else:
        # 如果是從 "我的課程" 列表取消，week_start 為 None，直接重載
        return redirect(url_for('frontdesk.member_home'))