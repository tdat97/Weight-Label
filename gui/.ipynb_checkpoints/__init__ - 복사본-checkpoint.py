from utils.logger import logger
from utils.text import *
from utils.value import ValueControl
from utils.table import TableManager
from utils.crypto import glance
from utils.paper import PaperManager
from utils import tool


import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as font
# import tkinter.filedialog as filedialog
from tkinter import messagebox as mb
from tkcalendar import DateEntry

from collections import defaultdict as ddict
from threading import Thread, Lock
from PIL import Image, ImageTk
import pandas as pd
import numpy as np
import traceback
import datetime
import pymysql
import serial
import json
import time
import os
import re

from json import JSONDecodeError

class MainWindow(tk.Tk):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.title(TITLE)
        
        # 셋팅값 가져오기
        try:
            with open(SETTING_PATH, "r", encoding='utf-8') as f:
                self.setting_dic = json.load(f)
        except:
            logger.error(traceback.format_exc())
            logger.warn("설정값 로딩 실패")
        
        # 아이콘 적용
        icon_path = self.setting_dic["icon_path"] if "icon_path" in self.setting_dic else None
        if os.path.isfile(icon_path): self.iconbitmap(icon_path)
        
        # 로코 이미지 가져오기
        logo_path = self.setting_dic["logo_path"] if "logo_path" in self.setting_dic else None
        self.logo_img_pil = Image.open(logo_path) if os.path.isfile(logo_path) else None
        
        # 화면 사이즈
        self.state("zoomed")
        self.geometry(f'{self.winfo_screenwidth()}x{self.winfo_screenheight()}')
        # self.geometry(f"{self.winfo_screenwidth()//5*2}x{self.winfo_screenheight()//5*2}")
        # self.minsize(self.winfo_screenwidth()//5*2, self.winfo_screenheight()//5*2)
        self.resizable(False, False)
        self.overrideredirect(True)
        
        # 글자크기 조정
        font_size_factor = self.setting_dic["font_size_factor"] if "font_size_factor" in self.setting_dic else 1920
        self.win_factor = self.winfo_screenwidth() / font_size_factor
        
        # 중량값들
        self.weight_value = 0.0
        self.bowl_value_control = ValueControl()
        self.measure_value = self.weight_value - self.bowl_value_control.real_value
        self.thr_lock = Lock()
        
        # 시리얼 연결
        try:
            self.my_serial = None
            port = self.setting_dic["serial_port"] if "serial_port" in self.setting_dic else "COM3"
            self.my_serial = serial.Serial(port, 9600)
        except:
            mb.showwarning(title="", message="중량계 연결 실패")
            logger.error(traceback.format_exc())
        
        # db 매니저
        add_cols = ['boowi', 'parm_nm']
        add_init = [' ', ' ']
        self.db_con = None
        db_info_dir = self.setting_dic["db_info_dir"] if "db_info_dir" in self.setting_dic else "../DB_pair/dev"
        nodb = self.setting_dic["nodb"] if "nodb" in self.setting_dic else True
        try:
            if nodb: raise Exception("NoDB mode.")
            # DB 정보 가져오기
            db_info_path = os.path.join(db_info_dir, DB_INFO_FILE)
            key_path = os.path.join(db_info_dir, KEY_FILE)
            db_info_str = glance(db_info_path, key_path)
            db_info_dic = json.loads(db_info_str)
            self.db_con = pymysql.connect(**db_info_dic, charset='utf8', autocommit=True)
            self.table_mng = TableManager(self.db_con, SQL_DIR_PATH, NODB_PATH, add_cols=add_cols,add_init=add_init)
        except JSONDecodeError:
            logger.warn("DB 정보 복호화 실패")
            mb.showwarning(title="", message="DB 정보 복호화 실패\n테스트버전으로 전환")
            self.table_mng = TableManager(None, SQL_DIR_PATH, NODB_PATH, add_cols=add_cols,add_init=add_init)
            logger.error(traceback.format_exc())
        except:
            logger.warn("DB 로드 실패")
            mb.showwarning(title="", message="DB 로드 실패...\n테스트 DB로 전환.")
            self.table_mng = TableManager(None, SQL_DIR_PATH, NODB_PATH, add_cols=add_cols,add_init=add_init)
            logger.error(traceback.format_exc())
        
        # 두번째 테이블 생성
        self.paper_keys = ["ITEM_CD", "ITEM_NM", "MFFART_RPT_NO", "boowi", "weight", "today", "EXPIRY_DT", 
                           "BUTCHERY_NM", "PLOR_CD", "STRG_TYPE", "HIS_NO", ]
        self.measure_keys = list(set(["ITEM_CD", "ITEM_NM", "weight", "HIS_NO", "number", *self.paper_keys]))
        self.measure_table = pd.DataFrame([], columns=self.measure_keys)
        
        # GUI 적용 및 bind
        self.__configure()
        self.set_bind()
        
        # 컬럼별 listbox
        lb_keys = ["ITEM_NM", "PROD_QTY", "BOX_IN_CNT", "STRG_TYPE", "BUNDLE_NO", "parm_nm", "BUTCHERY_NM", ]
        temp = [self.order_lb1, self.order_lb2, self.order_lb3, self.order_lb4, 
                self.order_lb5, self.order_lb6, self.order_lb7, ]
        self.lb_dic = dict(zip(lb_keys, temp))
        
        lb_keys = ["ITEM_CD", "ITEM_NM", "weight", "HIS_NO", "number", "print"]
        temp = [self.bar_lb1, self.bar_lb2, self.bar_lb3, self.bar_lb4, self.bar_lb5, self.bar_lb6, ]
        self.lb_dic2 = dict(zip(lb_keys, temp))
        
        # DB 가져오기
        self.update_table()
        # self.clear_table2()
        
        #
        self.stop_signal = False
        Thread(target=self.attach_logo, args=(), daemon=True).start()
        Thread(target=self.real_time_calc, args=(), daemon=True).start()
        Thread(target=self.real_time_get, args=(), daemon=True).start()
        Thread(target=self.test_stub, args=(), daemon=True).start()
        
        
    #######################################################################
    def attach_logo(self):
        if self.logo_img_pil is None: return
        wh, ww = self.logo_label.winfo_height(), self.logo_label.winfo_width()
        w, h = self.logo_img_pil.size
        magnf_value = min(wh/h, ww/w)
        
        self.logo_img_pil = self.logo_img_pil.resize((int(w*magnf_value), int(h*magnf_value)), Image.LANCZOS)
        self.logo_img_tk = ImageTk.PhotoImage(self.logo_img_pil)
        self.logo_label.configure(image=self.logo_img_tk)
        
    def real_time_calc(self):
        while not self.stop_signal:
            time.sleep(0.1)
            # calc
            self.measure_value = round(self.weight_value - self.bowl_value_control.real_value, 2)
            # print
            self.weight_label['text'] = str(self.weight_value)
            self.bowl_label['text'] = self.bowl_value_control.value_text
            self.measure_label['text'] = str(self.measure_value)
            
    def real_time_get(self):
        if self.my_serial is None: return
        
        while not self.stop_signal:
            data = self.my_serial.readline().decode('utf-8', errors='replace').strip()
            match = re.findall("\d+\.\d{2}", data)
            if match:
                self.weight_value = float(match[0])
            
    def test_stub(self):
        test = self.setting_dic["test_stub"] if "test_stub" in self.setting_dic else False
        if not test: return
        if self.my_serial is None: return
        
        while not self.stop_signal:
            time.sleep(2)
            data = np.random.randint(0, 10000) * 0.01
            self.my_serial.write(f"t e s t{data}t e s t\n".encode('utf-8'))
            
    #######################################################################
    def update_table(self, event=None):
        logger.info(f"UPDATE : {self.cal.get_date()}")
        
        # DB 다시 가져오기
        self.table_mng.excute_select(self.cal.get_date())
        
        # 리스트박스 업데이트
        for col in self.lb_dic:
            self.lb_dic[col].delete(0, 'end') # 청소
            for i in range(len(self.table_mng.df)):
                self.lb_dic[col].insert(i, self.table_mng.df.loc[i, col])
    
    def append_table2(self, idx, weight):
        # 목록에 추가
        idx = self.table_mng.df.iloc[idx].name
        i = len(self.measure_table)
        for col in self.measure_table.columns:
            if col in self.table_mng.df.columns:
                self.measure_table.loc[i, col] = self.table_mng.df.loc[idx, col]
        
        # 빈 열 추가
        # number, weight, today
        self.measure_table.loc[i, ["number", "weight", "today"]] = [i+1, weight, self.cal.get_date()]
        
        # 리스트박스 연장
        i = self.measure_table.iloc[-1].name
        for col in self.lb_dic2:
            if col in self.measure_table.columns:
                self.lb_dic2[col].insert('end', self.measure_table.loc[i, col])
        
        # 재인쇄 열 추가
        self.lb_dic2['print'].insert('end', '재인쇄')
        
    def clear_table2(self):
        # 여부묻기
        answer = mb.askquestion("모두지우기", "기록을 모두 지우겠습니까?")
        if answer == "no": return
        
        logger.info("CLEAR")
        
        # 리스트박스 청소
        for col in self.lb_dic2:
            self.lb_dic2[col].delete(0, 'end')
        
        # 테이블 청소
        self.measure_table = pd.DataFrame([], columns=self.measure_table.columns)
   
    #######################################################################
    def submit(self):
        # 선택검사
        tup = self.lb_dic['ITEM_NM'].curselection()
        if not tup:
            mb.showwarning(title="", message="품목명을 선택해 주세요.")
            return
        idx = tup[0]
        
        # 여부묻기
        name = self.lb_dic['ITEM_NM'].get(idx)
        weight = self.measure_value
        answer = mb.askquestion("인쇄하기", f"품목명 : {name}\n계량 : {weight} kg\n인쇄 하시겠습니까?")
        if answer == "no": return
    
        # 목록에 추가
        self.append_table2(idx, weight)
        
        # DB에 +1
        i = self.table_mng.df.iloc[idx].name
        order_no = self.table_mng.df.loc[i, 'ORDER_NO']
        self.table_mng.excute_update("GOOD_QTY", order_no)
        self.table_mng.excute_update("PROD_QTY", order_no)
        
        # table에 +1
        self.table_mng.df.loc[i, 'PROD_QTY'] += 1
        self.lb_dic['PROD_QTY'].delete(idx)
        self.lb_dic['PROD_QTY'].insert(idx, self.table_mng.df.loc[i, 'PROD_QTY'])
    
        # 인쇄
        self.print_label(len(self.measure_table) -1)
    
    def resubmit(self, event):
        # 가져오기
        tup = event.widget.curselection()
        if not tup: return
        idx = tup[0]
        
        # 순번 가져오기
        num = int(self.lb_dic2['number'].get(idx))
        
        # 여부묻기
        answer = mb.askquestion("인쇄하기", f"순번 : {num}\n해당 라벨을 \n인쇄 하시겠습니까?")
        if answer == "no": return
    
        # 인쇄
        self.print_label(idx)
    
    def print_label(self, idx):
        # 계량목록 리스트박스에서 마지막값 가져오기
        idx = self.measure_table.iloc[-1].name
        paper_info = self.measure_table.loc[idx, self.paper_keys].values
        
        # 데이터 수정
        paper_dic = dict(zip(self.paper_keys, paper_info))
        paper_dic = self.edit_data(paper_dic)
        logger.info(f"PRINT : {paper_dic}")
        
        # 이미지 만들기
        pix = self.setting_dic['n_pixel']
        paper_img = self.make_paper_img(paper_dic)
        paper_img = paper_img.resize((pix,pix))
        paper_img.save("test.png","PNG")
        
        # 진짜 인쇄
        real = self.setting_dic["real_print"] if "real_print" in self.setting_dic else True
        if real:
            tool.print_file(paper_img)
    
    def edit_data(self, paper_dic):
        for key in paper_dic:
            paper_dic[key] = str(paper_dic[key])
            
        temp = "{:0>6}".format(paper_dic["ITEM_CD"][-6:]) # 품목코드
        temp += "{:0>6}".format(re.sub('\-', '', paper_dic["today"])[-6:]) # 제조일자
        temp += "{:0>6}".format(re.sub('\.', '', paper_dic["weight"])[-6:]) # 중량
        temp += "{:0>2}".format(ddict(lambda:"01", {"F":"01", "C":"02"})[paper_dic["STRG_TYPE"]]) # 중량
        temp += "{:0>8}".format(np.random.randint(0, 10**8))
        paper_dic['bar1'] = temp
        
        # KOR -> 국내산
        dic = {'KOR':'국내산', 'AUS':'호주산', 'FRG':'미국산'}
        dic = ddict(lambda:'국내산', dic)
        paper_dic['PLOR_CD'] = dic[paper_dic['PLOR_CD']]
        
        # F -> 냉동보관
        dic = {'C':'-2℃~10℃ 냉장보관', 'F':'-18℃ 이하 냉동보관'}
        dic = ddict(lambda:'-18℃ 이하 냉동보관', dic)
        paper_dic['STRG_TYPE'] = dic[paper_dic['STRG_TYPE']]
        
        # weight -> kg
        paper_dic['weight'] = paper_dic['weight'] + " kg"
        
        return paper_dic
    
    def make_paper_img(self, paper_dic):
        # 싱글톤 객체 생성
        img_path = self.setting_dic["paper_img_path"]
        json_path = self.setting_dic["paper_json_path"]
        font_path = self.setting_dic["font_path"]
        paper_mng = PaperManager(img_path, json_path, font_path)
        
        paper_mng.reset()
        paper_mng.attach(paper_dic["ITEM_NM"], "제품명", barcode=False)
        paper_mng.attach(paper_dic["MFFART_RPT_NO"], "품목제조번호", barcode=False)
        paper_mng.attach(paper_dic["boowi"], "부위명", barcode=False)
        paper_mng.attach(paper_dic["weight"], "중량", barcode=False)
        paper_mng.attach(paper_dic["today"], "제조일자", barcode=False)
        paper_mng.attach(paper_dic["EXPIRY_DT"], "유통기한", barcode=False)
        paper_mng.attach(paper_dic["BUTCHERY_NM"], "도축장", barcode=False)
        paper_mng.attach(paper_dic["PLOR_CD"], "원산지", barcode=False)
        paper_mng.attach(paper_dic["STRG_TYPE"], "보관방법", barcode=False)
        options = {'module_width': 0.45, 'module_height': 18}
        paper_mng.attach("L12301305239001", "이력묶음번호", barcode=True, options=options)
        # paper_mng.attach(paper_dic["HIS_NO"], "이력묶음번호", barcode=True, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["bar1"], "바코드1", barcode=True, rotate_num=3, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["bar1"], "바코드2", barcode=True, rotate_num=3, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["bar1"], "바코드3", barcode=True, rotate_num=3, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["bar1"], "바코드4", barcode=True, rotate_num=3, options=options)
        
        return paper_mng.get_img()
    
    #######################################################################
    def input_pin(self, v):
        assert type(v) is str
        self.bowl_value_control.input_cmd(v)
        
    def weight2bowl(self):
        self.bowl_value_control.set_value(str(self.weight_value))
        
    def termination(self):
        self.stop_signal = True
        time.sleep(0.2)
        self.destroy()

    def on_closing(self):
        answer = mb.askquestion("종료하기", "종료 하시겠습니까?")
        if answer == "no": return
        Thread(target=self.termination, args=(), daemon=True).start()
        
    #######################################################################
    def set_bind(self):
        self.bar_lb6.bind("<Double-Button-1>", self.resubmit)
        self.cal.bind("<<DateEntrySelected>>", self.update_table)
    
    #######################################################################
    def __configure(self):
        # 배경
        bg_color = "#333F50"
        self.configure(bg=bg_color)
        
        # 최상단프레임
        self.top_frame = tk.Frame(self, bd=1, relief="solid", bg=bg_color)
        self.top_frame.place(relx=0.0, rely=0.0, relwidth=1, relheight=0.1)
        
        # 최상단프레임 - 로고
        self.logo_label = tk.Label(self.top_frame, bd=0, relief="solid") # "solid"
        self.logo_label.place(relx=0.0, rely=0.0, relwidth=0.1, relheight=1)
        self.logo_label.configure(image=None, bg=bg_color)
        
        # 최상단프레임 - 제목
        self.title_label = tk.Label(self.top_frame, bd=0, relief="solid") # "solid"
        self.title_label.place(relx=0.1, rely=0.0, relwidth=0.3, relheight=1)
        self.title_label['font'] = font.Font(family='Helvetica', size=int(50*self.win_factor), weight='bold')
        self.title_label.configure(text=TITLE, bg=bg_color, fg="#A6A6A6", anchor='center')
        
        # 최상단프레임 - 지시일라벨
        self.ord_label = tk.Label(self.top_frame, bd=0, text="지시일:", relief="solid") # "solid"
        self.ord_label.place(relx=0.4, rely=0.0, relwidth=0.1, relheight=1)
        self.ord_label['font'] = font.Font(family='Helvetica', size=int(25*self.win_factor), weight='bold')
        self.ord_label.configure(image=None, bg=bg_color, fg="#fff")
        
        # 최상단프레임 - 지시일선택
        self.cal = DateEntry(self.top_frame, selectmode='day',date_pattern='yyyy-MM-dd')
        self.cal.place(relx=0.5, rely=0.0, relwidth=0.2, relheight=1)
        self.cal['font'] = font.Font(family='Helvetica', size=int(35*self.win_factor), weight='bold')
        
        # 최상단프레임 - 조회
        self.bowl_btn = tk.Button(self.top_frame, bd=5, text="조회", command=self.cal.drop_down)
        self.bowl_btn.place(relx=0.7, rely=0.0, relwidth=0.1, relheight=1)
        self.bowl_btn['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        self.bowl_btn.configure(bg="#333", fg="#fff", activebackground="#fff", activeforeground="#333")
        
        # 최상단프레임 - 실측>용기
        self.bowl_btn = tk.Button(self.top_frame, bd=5, text="실측중량↓\n용기중량", command=self.weight2bowl)
        self.bowl_btn.place(relx=0.8, rely=0.0, relwidth=0.1, relheight=1)
        self.bowl_btn['font'] = font.Font(family='Helvetica', size=int(25*self.win_factor), weight='bold')
        self.bowl_btn.configure(bg="#333", fg="#fff", activebackground="#fff", activeforeground="#333")
        
        # 최상단프레임 - 종료하기
        self.back_btn = tk.Button(self.top_frame, bd=5, text="종료\n하기", command=self.on_closing)
        self.back_btn.place(relx=0.9, rely=0.0, relwidth=0.1, relheight=1)
        self.back_btn['font'] = font.Font(family='Helvetica', size=int(25*self.win_factor), weight='bold')
        self.back_btn.configure(bg="#333", fg="#ff0", activebackground="#ff0", activeforeground="#333")
        
        
        # 좌상단테이블프레임
        self.top_left_frame = tk.Frame(self, bd=10, relief=None, bg=bg_color)
        self.top_left_frame.place(relx=0.0, rely=0.1, relwidth=0.75, relheight=0.45)
        
        # 좌상단테이블프레임 - 라벨
        self.temp = tk.Label(self.top_left_frame, text="지시목록", fg="#fff", bg=bg_color, anchor='w')
        self.temp.place(relx=0.0, rely=0.0, relwidth=0.3, relheight=0.1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        
        # 좌상단테이블프레임 - 지시목록컬럼프레임
        self.order_col_frame = tk.Frame(self.top_left_frame, bd=0, relief="solid", bg=bg_color)
        self.order_col_frame.place(relx=0.0, rely=0.1, relwidth=1, relheight=0.1)
        
        # 좌상단테이블프레임 - 지시목록컬럼프레임 - 컬럼
        font_size = 15
        self.temp = tk.Label(self.order_col_frame, text="품목명", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.0, rely=0.0, relwidth=0.20, relheight=1)
        self.temp = tk.Label(self.order_col_frame, text="생산수량\n(BOX)", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.20, rely=0.0, relwidth=0.10, relheight=1)
        self.temp = tk.Label(self.order_col_frame, text="입수\n수량", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.30, rely=0.0, relwidth=0.05, relheight=1)
        self.temp = tk.Label(self.order_col_frame, text="보관\n유형", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.35, rely=0.0, relwidth=0.05, relheight=1)
        self.temp = tk.Label(self.order_col_frame, text="묶음번호", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.40, rely=0.0, relwidth=0.25, relheight=1)
        self.temp = tk.Label(self.order_col_frame, text="농가", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.65, rely=0.0, relwidth=0.15, relheight=1)
        self.temp = tk.Label(self.order_col_frame, text="도축장명", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.80, rely=0.0, relwidth=0.20, relheight=1)
        
        # 좌상단테이블프레임 - 지시목록리스트프레임
        self.order_list_frame = tk.Frame(self.top_left_frame, bd=0, relief="solid", bg=bg_color)
        self.order_list_frame.place(relx=0.0, rely=0.2, relwidth=1, relheight=0.8)
        
        # 좌상단테이블프레임 - 지시목록리스트프레임 - 리스트
        font_size = 25
        func = lambda x,y:(self.order_scrollbar.set(x,y),
                           self.order_lb1.yview("moveto",x), self.order_lb2.yview("moveto",x), 
                           self.order_lb3.yview("moveto",x), self.order_lb4.yview("moveto",x), 
                           self.order_lb5.yview("moveto",x), self.order_lb6.yview("moveto",x), 
                           self.order_lb7.yview("moveto",x), )
        self.order_lb1 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb1.place(relx=0.0, rely=0.0, relwidth=0.20, relheight=1.0)
        self.order_lb1['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.order_lb2 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb2.place(relx=0.20, rely=0.0, relwidth=0.10, relheight=1.0)
        self.order_lb2['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.order_lb3 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb3.place(relx=0.30, rely=0.0, relwidth=0.05, relheight=1.0)
        self.order_lb3['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.order_lb4 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb4.place(relx=0.35, rely=0.0, relwidth=0.05, relheight=1.0)
        self.order_lb4['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.order_lb5 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb5.place(relx=0.40, rely=0.0, relwidth=0.25, relheight=1.0)
        self.order_lb5['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.order_lb6 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb6.place(relx=0.65, rely=0.0, relwidth=0.15, relheight=1.0)
        self.order_lb6['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.order_lb7 = tk.Listbox(self.order_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.order_lb7.place(relx=0.80, rely=0.0, relwidth=0.20, relheight=1.0)
        self.order_lb7['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        
        self.order_scrollbar = tk.Scrollbar(self.order_list_frame, orient=tk.VERTICAL)
        self.order_scrollbar.pack(side="right", fill="y")
        
        func = lambda *args:(self.order_lb1.yview(*args), self.order_lb2.yview(*args), self.order_lb3.yview(*args), 
                             self.order_lb4.yview(*args), self.order_lb5.yview(*args), self.order_lb6.yview(*args), 
                             self.order_lb7.yview(*args), )
        self.order_scrollbar.config(command=func)
        
        for i in range(20):
            self.order_lb1.insert(tk.END, f"test{i:02d}")
            self.order_lb2.insert(tk.END, f"test{i:02d}")
            self.order_lb3.insert(tk.END, f"test{i:02d}")
            self.order_lb4.insert(tk.END, f"test{i:02d}")
            self.order_lb5.insert(tk.END, f"test{i:02d}")
            self.order_lb6.insert(tk.END, f"test{i:02d}")
            self.order_lb7.insert(tk.END, f"test{i:02d}")
        
        
        # 좌하단테이블프레임
        self.bot_left_frame = tk.Frame(self, bd=10, relief=None, bg=bg_color)
        self.bot_left_frame.place(relx=0.0, rely=0.55, relwidth=0.75, relheight=0.45)
        
        # 좌하단테이블프레임 - 라벨
        self.temp = tk.Label(self.bot_left_frame, text="BOX 바코드 계량 목록", fg="#fff", bg=bg_color, anchor='w')
        self.temp.place(relx=0.0, rely=0.0, relwidth=0.3, relheight=0.1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        
        # 좌하단테이블프레임 - 바코드목록컬럼프레임
        self.bar_col_frame = tk.Frame(self.bot_left_frame, bd=0, relief="solid", bg=bg_color)
        self.bar_col_frame.place(relx=0.0, rely=0.1, relwidth=1, relheight=0.1)
        
        # 좌하단테이블프레임 - 바코드목록컬럼프레임 - 컬럼
        font_size = 15
        self.temp = tk.Label(self.bar_col_frame, text="품목코드", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.0, rely=0.0, relwidth=0.15, relheight=1)
        self.temp = tk.Label(self.bar_col_frame, text="품목명", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.15, rely=0.0, relwidth=0.25, relheight=1)
        self.temp = tk.Label(self.bar_col_frame, text="계량중량", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.40, rely=0.0, relwidth=0.10, relheight=1)
        self.temp = tk.Label(self.bar_col_frame, text="이력번호", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.50, rely=0.0, relwidth=0.25, relheight=1)
        self.temp = tk.Label(self.bar_col_frame, text="순번", bg="#B6E2E4", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.temp.place(relx=0.75, rely=0.0, relwidth=0.10, relheight=1)
        self.clear_btn = tk.Button(self.bar_col_frame, bd=2, text="모두지우기", command=self.clear_table2)
        self.clear_btn.place(relx=0.85, rely=0.0, relwidth=0.15, relheight=1)
        self.clear_btn['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.clear_btn.configure(bg="#FF5050", fg="#fff", activebackground="#fff", activeforeground="#FF5050")
        # self.temp = tk.Label(self.bar_col_frame, text="", bg="#B6E2E4", fg="#F00", relief="solid", bd=1)
        # self.temp['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        # self.temp.place(relx=0.85, rely=0.0, relwidth=0.15, relheight=1)
        
        # 좌하단테이블프레임 - 바코드목록컬럼프레임
        self.bar_list_frame = tk.Frame(self.bot_left_frame, bd=0, relief="solid", bg=bg_color)
        self.bar_list_frame.place(relx=0.0, rely=0.2, relwidth=1, relheight=0.8)
        
        # 좌하단테이블프레임 - 바코드목록컬럼프레임 - 리스트
        font_size = 25
        func = lambda x,y:(self.bar_scrollbar.set(x,y),
                           self.bar_lb1.yview("moveto",x), self.bar_lb2.yview("moveto",x), 
                           self.bar_lb3.yview("moveto",x), self.bar_lb4.yview("moveto",x), 
                           self.bar_lb5.yview("moveto",x), self.bar_lb6.yview("moveto",x), )
        self.bar_lb1 = tk.Listbox(self.bar_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.bar_lb1.place(relx=0.0, rely=0.0, relwidth=0.15, relheight=1.0)
        self.bar_lb1['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.bar_lb2 = tk.Listbox(self.bar_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.bar_lb2.place(relx=0.15, rely=0.0, relwidth=0.25, relheight=1.0)
        self.bar_lb2['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.bar_lb3 = tk.Listbox(self.bar_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.bar_lb3.place(relx=0.40, rely=0.0, relwidth=0.10, relheight=1.0)
        self.bar_lb3['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.bar_lb4 = tk.Listbox(self.bar_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.bar_lb4.place(relx=0.50, rely=0.0, relwidth=0.25, relheight=1.0)
        self.bar_lb4['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.bar_lb5 = tk.Listbox(self.bar_list_frame, yscrollcommand=func, bg="#fff", fg="#000")
        self.bar_lb5.place(relx=0.75, rely=0.0, relwidth=0.10, relheight=1.0)
        self.bar_lb5['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        self.bar_lb6 = tk.Listbox(self.bar_list_frame, yscrollcommand=func, bg="#fff", fg="#f00")
        self.bar_lb6.place(relx=0.85, rely=0.0, relwidth=0.15, relheight=1.0)
        self.bar_lb6['font'] = font.Font(family='Helvetica', size=int(font_size*self.win_factor), weight='bold')
        
        self.bar_scrollbar = tk.Scrollbar(self.bar_list_frame, orient=tk.VERTICAL)
        self.bar_scrollbar.pack(side="right", fill="y")
        
        func = lambda *args:(self.bar_lb1.yview(*args), self.bar_lb2.yview(*args), self.bar_lb3.yview(*args), 
                             self.bar_lb4.yview(*args), self.bar_lb5.yview(*args), self.bar_lb6.yview(*args), )
        self.bar_scrollbar.config(command=func)
        
        # for i in range(20):
        #     self.bar_lb1.insert(tk.END, f"test{i:02d}")
        #     self.bar_lb2.insert(tk.END, f"test{i:02d}")
        #     self.bar_lb3.insert(tk.END, f"test{i:02d}")
        #     self.bar_lb4.insert(tk.END, f"test{i:02d}")
        #     self.bar_lb5.insert(tk.END, f"test{i:02d}")
        #     self.bar_lb6.insert(tk.END, f"test{i:02d}")
        
        
        
        
        # 우상단프레임
        self.top_right_frame = tk.Frame(self, bd=10, relief="flat", bg=bg_color)
        self.top_right_frame.place(relx=0.75, rely=0.1, relwidth=0.25, relheight=0.45)
        
        # 우상단프레임 - 계량정보들
        self.temp = tk.Label(self.top_right_frame, text="실측중량", bg="#D0CECE", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        self.temp.place(relx=0.0, rely=0.0, relwidth=0.4, relheight=0.2)
        self.temp = tk.Label(self.top_right_frame, text="용기중량", bg="#D0CECE", fg="#000", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        self.temp.place(relx=0.0, rely=0.2, relwidth=0.4, relheight=0.2)
        self.temp = tk.Label(self.top_right_frame, text="계량", bg="#2CB1AE", fg="#fff", relief="solid", bd=1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(50*self.win_factor), weight='bold')
        self.temp.place(relx=0.0, rely=0.4, relwidth=0.4, relheight=0.3)
        self.weight_label = tk.Label(self.top_right_frame, text="88.88", bg="#fff", fg="#000", relief="solid", bd=1)
        self.weight_label['font'] = font.Font(family='Helvetica', size=int(45*self.win_factor), weight='bold')
        self.weight_label.place(relx=0.4, rely=0.0, relwidth=0.6, relheight=0.2)
        self.bowl_label = tk.Label(self.top_right_frame, text="88.88", bg="#fff", fg="#000", relief="solid", bd=1)
        self.bowl_label['font'] = font.Font(family='Helvetica', size=int(45*self.win_factor), weight='bold')
        self.bowl_label.place(relx=0.4, rely=0.2, relwidth=0.6, relheight=0.2)
        self.measure_label = tk.Label(self.top_right_frame, text="0.00", bg="#fff", fg="#000", relief="solid", bd=1)
        self.measure_label['font'] = font.Font(family='Helvetica', size=int(60*self.win_factor), weight='bold')
        self.measure_label.place(relx=0.4, rely=0.4, relwidth=0.6, relheight=0.3)
        self.print_btn = tk.Button(self.top_right_frame, text="인쇄", bd=5, command=self.submit)
        self.print_btn.place(relx=0.0, rely=0.7, relwidth=1, relheight=0.3)
        self.print_btn['font'] = font.Font(family='Helvetica', size=int(60*self.win_factor), weight='bold')
        self.print_btn.configure(bg="#FF5050", fg="#fff", activebackground="#fff", activeforeground="#FF5050")
        
        
        
        # 우하단프레임
        self.bot_right_frame = tk.Frame(self, bd=10, relief="flat", bg=bg_color)
        self.bot_right_frame.place(relx=0.75, rely=0.55, relwidth=0.25, relheight=0.45)
        
        # 우하단프레임 - 라벨
        self.temp = tk.Label(self.bot_right_frame, text="용기중량 입력패드", fg="#fff", bg=bg_color, anchor='w')
        self.temp.place(relx=0.0, rely=0.0, relwidth=1, relheight=0.1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        
        
        # 우하단프레임 - 버튼프레임
        self.button_frame = tk.Frame(self.bot_right_frame, bd=0, relief="flat", bg=bg_color)
        self.button_frame.place(relx=0.0, rely=0.1, relwidth=1, relheight=0.9)
        
        # 우하단프레임 - 버튼프레임 - 버튼들
        pin_list = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '←', '0', '.']
        for i, v in enumerate(pin_list):
            pin_btn = tk.Button(self.button_frame, bd=5, text=v, command=lambda x=v:self.input_pin(x))
            pin_btn['font'] = font.Font(family='Helvetica', size=int(70*self.win_factor), weight='bold')
            pin_btn.configure(bg="#BFBFBF", fg="#FF5050", activebackground="#FF5050", activeforeground="#BFBFBF")
            pin_btn.place(relx=0.3333*(i%3), rely=0.25*(i//3), relwidth=0.3333, relheight=0.25)
            
        
        
        
        
        