# link.py
#
# 這個檔以前用來做資料庫連線，
# 但現在所有 DB 邏輯都搬到 api/sql.py 裡了。
# 為了相容舊程式裡的 `from link import *`，
# 保留這個檔案，但不再做任何連線動作。

# 如果之後真的有需要，可以在這裡
# 從 api.sql 匯入需要的東西，例如：
#
# from api.sql import DB, Member, Coach, Plan, Course, CourseSchedule, Booking, ConfirmSQL, Analysis
#
# 目前先留空，避免在匯入時就嘗試連線導致 Render 直接啟動失敗。
