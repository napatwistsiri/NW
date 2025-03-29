import threading
from smartcard.System import readers
from smartcard.util import toHexString
from ftplib import FTP
import time
import json
from datetime import datetime

# ฐานข้อมูลของบัตร NFC พร้อมยอดเงิน
card_balance = {
    "56632303": 500,   # 56 63 23 03
    "1ABB2303": 300,   # 1A BB 23 03
    "8B052403": 700,   # 8B 05 24 03
    "B6CA2303": 1000,  # B6 CA 23 03
    "2C592303": 150    # 2C 59 23 03
}

# ฟังก์ชันตรวจสอบยอดเงินจากฐานข้อมูล
def check_balance(card_id):
    balance = card_balance.get(card_id, 0)  # หากไม่มีข้อมูลคืนค่า 0
    transaction_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # เก็บวันและเวลา

    if balance < 200:
        print(f"ยอดเงินไม่พอ(ยอดเงินคงเหลือ: {balance} บาท)\n ไม่เปิดประตู")
        
        # บันทึกประวัติเมื่อยอดเงินไม่พอ
        insufficient_funds_data = {
            "uid": card_id,
            "balance": balance,
            "transaction_time": transaction_time,
            "status": "Insufficient funds",
            "message": "ไม่เปิดประตูได้"
        }
        json_data = json.dumps(insufficient_funds_data, indent=4)
        upload_data_to_ftp(json_data, "insufficient_funds.json")
        
        return False
    else:
        print(f"ยอดเงินคงเหลือ: {balance} บาท")
        return True

# ฟังก์ชันคำนวณค่าธรรมเนียมจากทางเข้าและทางออก
def calculate_fee(entry_point, exit_point):
    fee_rates = {
        ("entry1", "exit1"): 50,  # ค่าธรรมเนียมสำหรับ entry1 -> exit1
        ("entry1", "exit2"): 60,  # ค่าธรรมเนียมสำหรับ entry1 -> exit2
        ("entry2", "exit1"): 70,  # ค่าธรรมเนียมสำหรับ entry2 -> exit1
        ("entry2", "exit2"): 80,  # ค่าธรรมเนียมสำหรับ entry2 -> exit2
        ("entry3", "exit3"): 100  # ค่าธรรมเนียมสำหรับ entry3 -> exit3
    }

    fee = fee_rates.get((entry_point, exit_point), 100)  # Default fee is 100
    print(f"ค่าธรรมเนียมที่ต้องจ่าย: {fee} บาท")
    return fee

# ฟังก์ชันบันทึกข้อมูลและส่งไปยัง FTP Server
def upload_data_to_ftp(data, filename):
    try:
        ftp = FTP("ftp.server.com")  # ระบุ FTP server ที่ใช้งาน
        ftp.login(user="your_username", passwd="your_password")
        ftp.cwd("/path/to/directory")

        # เปิดไฟล์ในโหมด 'w' เพื่อเขียนข้อมูล
        with open(filename, "w") as f:
            f.write(data)

        # เปิดไฟล์ในโหมด 'rb' และอัปโหลดไปยัง FTP server
        with open(filename, "rb") as f:
            ftp.storbinary(f"STOR {filename}", f)

        ftp.quit()
        print(f"อัปโหลด {filename} สำเร็จ")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการอัปโหลดไฟล์: {e}")

# ฟังก์ชันเชื่อมต่อกับ NFC Reader
def nfc_reader():
    r = readers()
    if len(r) < 1:
        print("ไม่พบเครื่องอ่านบัตร NFC!")
        return

    reader = r[0]
    print("ใช้เครื่องอ่าน:", reader)

    connection = reader.createConnection()

    while True:
        try:
            connection.connect()
            GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(GET_UID)
            uid = toHexString(data).replace(' ', '').upper()  # เปลี่ยนให้เป็นรูปแบบเดียวกับในฐานข้อมูล
            print(f"UID ที่ได้จากบัตรคือ: {uid}")  # แสดง UID ที่ได้จากบัตร

            # ตรวจสอบยอดเงินจาก card_id ที่ได้
            if check_balance(uid):
                # กำหนด entry_point และ exit_point สำหรับการคำนวณค่าธรรมเนียม
                entry_point = "entry1"  # ตัวอย่างกำหนดเป็น entry1
                exit_point = "exit1"    # ตัวอย่างกำหนดเป็น exit1

                # คำนวณค่าธรรมเนียมจากทางเข้าและทางออก
                fee = calculate_fee(entry_point, exit_point)
                
                # หักยอดเงินจากบัญชี
                if card_balance[uid] >= fee:
                    card_balance[uid] -= fee
                    print(f"หักยอดจากบัญชี: {fee} บาท")
                    
                    # บันทึกวันที่และเวลาของการทำรายการ
                    transaction_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # สร้างข้อมูลการทำธุรกรรม
                    transaction_data = f"User {uid} paid {fee} THB. Remaining balance: {card_balance[uid]} on {transaction_time}"
                    upload_data_to_ftp(transaction_data, "data.txt")
                    
                    # เปิดประตู (จำลองการเปิดประตูโดยการรอ 3 วินาที)
                    print("เปิดประตู")
                    time.sleep(3)  # ดีเลย์ 3 วินาทีก่อนเปิดประตู
        
                    # เก็บข้อมูล UID และยอดเงินในไฟล์ JSON พร้อมวันที่และเวลา และอัปโหลด
                    card_info = {"uid": uid, "balance": card_balance[uid], "transaction_time": transaction_time}
                    json_data = json.dumps(card_info, indent=4)
                    upload_data_to_ftp(json_data, "FTPserver.json")
                else:
                    print(f"ไม่สามารถหักเงินได้เนื่องจากยอดเงินไม่พอ")
            time.sleep(3)  # รอ 3 วินาที ก่อนอ่านบัตรครั้งถัดไป
        except Exception as e:
            print("เกิดข้อผิดพลาด:", e)
            time.sleep(3)

# สร้าง Thread สำหรับ NFC Reader และทำงานแยกต่างหาก
def start_nfc_reader_thread():
    nfc_thread = threading.Thread(target=nfc_reader)
    nfc_thread.start()

# เริ่มทำงาน
if __name__ == "__main__":
    start_nfc_reader_thread()
