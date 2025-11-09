import imp
from flask import render_template, Blueprint, redirect, request, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
# from link import *
from api.sql import * # 假設這裡有 Member 和 Coach 的 SQL 操作 Class

api = Blueprint('api', __name__, template_folder='./templates')

login_manager = LoginManager(api)
login_manager.login_view = 'api.login'
login_manager.login_message = "請先登入"

class User(UserMixin):
    pass

@login_manager.user_loader
def user_loader(userid): # userid 格式為 'member_M0000001' 或 'coach_T0001'
    """
    根據 flask_login 儲存的 userid (帶有前綴)，
    從正確的資料表 (Member 或 Coach) 載入使用者資訊。
    """
    user = User()
    user.id = userid
    
    try:
        # 分割 userid, 例如 'member_M0000001' -> ['member', 'M0000001']
        role, id = userid.split('_', 1) 
        
        if role == 'member':
            data = Member.get_by_id(id) 
            user.role = 'member'
            user.name = data[0][0] # data = (mName, password)
        elif role == 'coach':
            data = Coach.get_by_id(id)
            user.role = 'coach'
            user.name = data[0][0] # data = (cName, password)
            
    except Exception as e:
        print(f"user_loader 錯誤: {e}") # 偵錯用
        pass
    return user

@api.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        # 這個 'account' 欄位現在代表 'memberId' 或 'coachId'
        account_id = request.form['account'] 
        password = request.form['password']

        # 策略：先嘗試將 account_id 視為 memberId
        member_data = Member.get_by_id(account_id) 

        if member_data:
            DB_password = member_data[0][1] # member_data = (mName, password)
            
            if DB_password == password:
                user = User()
                user.id = f"member_{account_id}" # 加上 'member_' 前綴
                login_user(user)
                # 登入成功，導向課程預約頁面
                return redirect(url_for('frontdesk.member_home'))
            else:
                flash('*密碼錯誤')
                return redirect(url_for('api.login'))

        # 如果不是 Member，再嘗試將 account_id 視為 coachId
        coach_data = Coach.get_by_id(account_id)
        
        if coach_data:
            DB_password = coach_data[0][1] # coach_data = (cName, password)
            
            if DB_password == password:
                user = User()
                user.id = f"coach_{account_id}" # 加上 'coach_' 前綴
                login_user(user)
                # 登入成功，導向教練後台 (名稱待修改)
                return redirect(url_for('manager.courseManager'))
            else:
                flash('*密碼錯誤')
                return redirect(url_for('api.login'))

        # 如果兩個資料表都找不到
        flash('*查無此帳號')
        return redirect(url_for('api.login'))
    
    return render_template('login.html')

@api.route('/register', methods=['POST', 'GET'])
def register():
    """
    處理註冊，根據 'identity' 欄位決定寫入 Member 還是 Coach 資料表。
    """
    if request.method == 'POST':
        identity = request.form['identity'] # 假設前端有 'identity' (value: 'member' 或 'coach')
        password = request.form['password']

        try:
            if identity == 'member':
                # 1. 取得 Member 表單所有欄位
                member_id = request.form['userId']
                
                # 2. 檢查 memberId 是否已被註冊
                if Member.get_by_id(member_id):
                    flash('此會員 ID 已被註冊')
                    return redirect(url_for('api.register'))

                input_data = {
                    'memberId': member_id, # 會員 ID (登入帳號)
                    'mName': request.form['mName'],
                    'birthDate': request.form['birthDate'],
                    'gender': request.form['gender'],
                    'phoneNumber': request.form['phoneNumber'],
                    'password': password
                    # 'registerDate' 應由 SQL 的 NOW() 產生
                    # 'status' 應設為預設值 (例如 'pending_contract')
                    # 'planId' 應為 NULL
                }
                
                # 3. 建立會員
                Member.create_member(input_data)
                flash('會員註冊成功！請登入並完成合約簽署')
                
            elif identity == 'coach':
                # 1. 取得 Coach 表單所有欄位
                coach_id = request.form['userId'] # 教練 ID

                # 2. 檢查 Coach ID 是否已被註冊
                #    使用上面 login 也在用的 Coach.get_by_coachId()
                if Coach.get_by_id(coach_id):
                    flash('此教練代碼已被註冊')
                    return redirect(url_for('api.register'))

                input_data = {
                    'coachId': coach_id, 
                    'cName': request.form['cName'],
                    'coachingType': request.form['coachingType'],
                    'password': password
                    # 'class' 欄位在 DDL 中，依需求加入
                }

                # 3. 建立教練
                # !!注意: 您需要在 sql.py 中建立 Coach.create_coach(input_data) 函式
                Coach.create_coach(input_data)
                flash('教練註冊成功！請登入')

            else:
                flash('無效的身分')
                return redirect(url_for('api.register'))

            # 不論註冊身分為何，成功後都導向登入頁
            return redirect(url_for('api.login'))

        except Exception as e:
            flash(f'註冊失敗: {e}')
            return redirect(url_for('api.register'))

    return render_template('register.html')

@api.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))