from utils.logger import logger
from utils.text import *
from utils.value import ValueControl
from utils.table import TableManager, NodbManager
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
        
        # 중량계(시리얼) 연결
        try:
            self.my_serial = None
            port = self.setting_dic["serial_port"] if "serial_port" in self.setting_dic else "COM3"
            self.my_serial = serial.Serial(port, 9600)
        except:
            mb.showwarning(title="", message="중량계 연결 실패")
            logger.error(traceback.format_exc())
        
        # db 매니저
        db_info_dir = self.setting_dic["db_info_dir"] if "db_info_dir" in self.setting_dic else "../DB_pair/dev"
        nodb = self.setting_dic["nodb"] if "nodb" in self.setting_dic else True
        try:
            if nodb: raise Exception("NoDB mode.")
            # DB 정보 가져오기
            db_info_path = os.path.join(db_info_dir, DB_INFO_FILE)
            key_path = os.path.join(db_info_dir, KEY_FILE)
            self.table_mng = TableManager(SQL_DIR_PATH, db_info_path, key_path)
        except JSONDecodeError:
            logger.warn("DB 정보 복호화 실패")
            logger.error(traceback.format_exc())
            mb.showwarning(title="", message="DB 정보 복호화 실패\n테스트버전으로 전환")
            self.table_mng = NodbManager()
        except:
            logger.warn("DB 로드 실패")
            logger.error(traceback.format_exc())
            mb.showwarning(title="", message="DB 로드 실패...\n테스트 DB로 전환.")
            self.table_mng = NodbManager()
        
        # 라벨지에 들어가는 키
        self.paper_keys = ["ITEM_CD", "ITEM_NM", "MFFART_RPT_NO", "BOX_WGT", "PRINT_DT", "EXPIRY_DT", 
                           "BUTCHERY_NM", "PLOR_CD", "STRG_TYPE", "HIS_NO", "BOX_BARCODE"]
        
        # DB 인쇄목록에 들어가는 키
        self.insert_keys = ['ORDER_NO', 'BOX_BARCODE', 'WLOT_NO', 'PRINT_CNT', 'PRINT_DT', 
                            'BOX_IN_CNT', 'BOX_WGT', 'ITEM_CD', 'ITEM_NM', 'PLOR_CD']
        
        # self.table2_keys = list(set(["ORDER_NO", "ORDER_DT", "ITEM_CD", "ITEM_NM", "WLOT_NO",
        #                               "BOX_WGT", "HIS_NO", "BOX_BARCODE", *self.paper_keys]))
        
        # 테이블 생성
        self.table1 = pd.DataFrame([], columns=[])
        self.table2 = pd.DataFrame([], columns=[])
        
        # 트리뷰 컬럼 정의
        self.tree_cols1 = ["number", "ITEM_NM", "PROD_QTY", "BOX_IN_CNT", "STRG_TYPE", "BUNDLE_NO", 
                           "BUTCHERY_NM", "ORDER_ST"]
        self.tree_cols2 = ["number", "ORDER_DT", "ITEM_CD", "ITEM_NM", "BOX_WGT", "HIS_NO", ]
        self.tree_colnames1 = ['순번', '품목명', '생산(BOX)', '입수수량', '보관유형', '묶음번호', '도축장명', '상태']
        self.tree_colnames2 = ['순번', '지시일', '품목코드', '품목명', '계량중량', '이력번호', ]
        self.tree_widths1 = [0.05, 0.30, 0.10, 0.10, 0.10, 0.15, 0.15, 0.05]
        self.tree_widths2 = [0.05, 0.15, 0.10, 0.35, 0.10, 0.25]
        
        # GUI 적용 및 bind
        self.__configure()
        self.set_bind()
        
        # DB 가져오기
        self.update_table()
        
        # 트리뷰2 청소
        # for item_id in self.treeview2.get_children():
        #     self.treeview2.delete(item_id)
        
        # 쓰레드 실행
        self.stop_signal = False
        Thread(target=self.attach_logo, args=(), daemon=True).start()
        Thread(target=self.real_time_calc, args=(), daemon=True).start()
        Thread(target=self.real_time_get, args=(), daemon=True).start()
        Thread(target=self.test_stub, args=(), daemon=True).start()
        Thread(target=self.resize_treeview, args=(), daemon=True).start()
        
        
    #######################################################################
    # 실행하자마자
    
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
            
    def resize_treeview(self):
        time.sleep(0.1)
        
        # 첫번째 treeview 너비 수정
        width = self.treeview1.winfo_width()
        for col, ratio in zip(self.tree_cols1, self.tree_widths1):
            self.treeview1.column(col, width=int(width*ratio), minwidth=int(width*ratio))
            
        # 두번째 treeview 너비 수정
        width = self.treeview2.winfo_width()
        for col, ratio in zip(self.tree_cols2, self.tree_widths2):
            self.treeview2.column(col, width=int(width*ratio), minwidth=int(width*ratio))
            
        # treeview 정렬
        self.treeview1.column('PROD_QTY', anchor='e')
        self.treeview1.column('BOX_IN_CNT', anchor='e')
        self.treeview1.column('STRG_TYPE', anchor='center')
        self.treeview2.column('BOX_WGT', anchor='e')
        
    #######################################################################
    # 인쇄버튼
    
    def submit(self):
        # 선택검사
        item_ids = self.treeview1.selection()
        if not item_ids:
            mb.showwarning(title="", message="품목명을 선택해 주세요.")
            return
        item_id1 = item_ids[0]
        
        # 선택행에서 원하는 값 찾기
        item_nm = self.table1.loc[item_id1, 'ITEM_NM']
        
        # 여부묻기
        weight = self.measure_value
        answer = mb.askquestion("인쇄하기", f"품목명 : {item_nm}\n계량 : {weight} kg\n인쇄 할까요?")
        if answer == "no": return
    
        # 목록에 추가
        self.append_table2(item_id1, weight)
        
        # DB에 +1
        order_no = self.table1.loc[item_id1, 'ORDER_NO']
        self.table_mng.execute_update("table1", "GOOD_QTY", "GOOD_QTY+1", order_no)
        self.table_mng.execute_update("table1", "PROD_QTY", "PROD_QTY+1", order_no)
        logger.info(f"UPDATE : {order_no} - detail : QTY+1")
        
        # table1에 +1
        self.table1.loc[item_id1, 'PROD_QTY'] += 1
        
        # 트리뷰1에 +1
        cols = list(self.treeview1['columns'])
        self.treeview1.item(item_id1, values=list(self.table1.loc[item_id1, cols]))
    
        # 마지막 행 인쇄
        item_id2 = self.table2.iloc[-1].name
        self.print_label(item_id2)
    
    def append_table2(self, item_id1, weight):
        # 목록에 추가
        for col in self.table2.columns:
            if col in self.table1.columns:
                self.table2.loc["temp", col] = self.table1.loc[item_id1, col]
        
        # treeview 빈 행 추가
        item_id2 = self.treeview2.insert('', 'end')
            
        # 열 추가
        # number, weight, today
        self.table2.loc["temp", ["number", "BOX_WGT", "PRINT_DT", "PRINT_CNT"]] = [item_id2, weight, self.cal.get_date(), 1]
        
        # 바코드 조합
        item_cd, print_dt, box_wgt, strg_type = self.table2.loc['temp', ["ITEM_CD", "PRINT_DT", "BOX_WGT", "STRG_TYPE"]]
        temp = "{:0>6}".format(item_cd[-6:]) # 품목코드
        temp += "{:0>6}".format(re.sub('\-', '', str(print_dt))[-6:]) # 제조일자
        temp += "{:0>6}".format(re.sub('\.', '', str(box_wgt))[-6:]) # 중량
        temp += "{:0>2}".format(ddict(lambda:"01", {"F":"01", "C":"02"})[strg_type]) # 중량
        temp += "{:0>8}".format(np.random.randint(0, 10**8))
        self.table2.loc["temp", "BOX_BARCODE"] = temp
        
        # treeview2 빈 행 수정
        cols = list(self.treeview2['columns'])
        self.treeview2.item(item_id2, values=list(self.table2.loc["temp", cols]))
        
        # 테이블2 temp행의 인덱스를 트리뷰2 item_id
        self.table2.rename(index={'temp':item_id2}, inplace=True)
        
        # db에 한줄 추가
        self.table_mng.execute_insert('table2', *self.table2.loc[item_id2, self.insert_keys])
        logger.info(f"INSERT : {self.table2.loc[item_id2, 'BOX_BARCODE']}")
    
    #######################################################################
    # 지시종료 버튼
    
    def finish_order(self):
        # 선택검사
        item_ids = self.treeview1.selection()
        if not item_ids:
            mb.showwarning(title="", message="지시종료할 행을 선택해 주세요.")
            return
        item_id1 = item_ids[0]
        
        # DB에 적용
        order_no = self.table1.loc[item_id1, "ORDER_NO"]
        self.table_mng.execute_update("table1", "ORDER_ST", "'END'", order_no)
        logger.info(f"UPDATE : {order_no} - detail : END")
        
        # table1에 적용
        self.table1.loc[item_id1, "ORDER_ST"] = "종료"
        
        # 트리뷰1에 적용
        cols = list(self.treeview1['columns'])
        self.treeview1.item(item_id1, values=list(self.table1.loc[item_id1, cols]))
    
    #######################################################################
    # 되돌리기 버튼
    
    def undo_append(self):
        # 선택검사
        item_ids = self.treeview2.selection()
        if not item_ids:
            mb.showwarning(title="", message="되돌릴 행을 선택해 주세요.")
            return
        item_id2 = item_ids[0]
        
    
        # ORDER_NO 가져오기
        order_no = self.table2.loc[item_id2, 'ORDER_NO']
        
        # 테이블1에서 찾기
        df = self.table1
        item_ids = list(df[df["ORDER_NO"] == order_no].iloc[:1].index)
        if not item_ids: mb.showwarning(title="", message="지시목록에 일치하는 행이 없어요.\n지시일을 확인해 주세요.")
        item_id1 = item_ids[0]
        
        # 여부묻기
        weight = self.measure_value
        answer = mb.askquestion("되돌리기", f"순번 : {item_id2}\n되돌릴까요?")
        if answer == "no": return
    
        # DB에서 없애기
        self.table_mng.execute_delete("table2", self.table2.loc[item_id2, "BOX_BARCODE"])
        logger.info(f"DELETE : {self.table2.loc[item_id2, 'BOX_BARCODE']}")
        
        # 테이블2에서 없애기
        self.table2.drop(item_id2, inplace=True)
        
        # 트리뷰2에서 없애기
        self.treeview2.delete(item_id2)
        
        # 테이블1에서 -1
        self.table1.loc[item_id1, 'PROD_QTY'] -= 1
        
        # 트리뷰1에서 -1
        cols = list(self.treeview1['columns'])
        self.treeview1.item(item_id1, values=list(self.table1.loc[item_id1, cols]))
        
        # DB에서 -1
        self.table_mng.execute_update("table1", "GOOD_QTY", "GOOD_QTY-1", order_no)
        self.table_mng.execute_update("table1", "PROD_QTY", "PROD_QTY-1", order_no)
        logger.info(f"UPDATE : {order_no} - detail : QTY-1")
        
    #######################################################################
    # 재인쇄 버튼
    
    def resubmit(self):
        # 선택검사
        item_ids = self.treeview2.selection()
        if not item_ids:
            mb.showwarning(title="", message="재인쇄하고 싶은 행을\n선택해 주세요.")
            return
        item_id2 = item_ids[0]
        
        # 여부묻기
        answer = mb.askquestion("인쇄하기", f"순번 : {item_id2}\n해당 라벨을 \n재인쇄 할까요?")
        if answer == "no": return
    
        # table +1, DB +1
        self.table2.loc[item_id2, "PRINT_CNT"] += 1
        barcode = self.table2.loc[item_id2, "BOX_BARCODE"]
        self.table_mng.execute_update("table2", "PRINT_CNT", "PRINT_CNT+1", barcode)
        logger.info(f"UPDATE : {barcode} - detail : CNT+1")
    
        # 인쇄
        self.print_label(item_id2)
    
    def print_label(self, item_id2):
        # 계량목록 테이블에서 값 가져오기
        paper_info = self.table2.loc[item_id2, self.paper_keys].values
        
        # 데이터 수정
        paper_dic = dict(zip(self.paper_keys, paper_info))
        paper_dic = self.edit_data(paper_dic)
        logger.info(f"paper_dic : {paper_dic}")
        
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
        
        # KOR -> 국내산
        dic = {'KOR':'국내산', 'AUS':'호주산', 'FRG':'미국산'}
        dic = ddict(lambda:'국내산', dic)
        paper_dic['PLOR_CD'] = dic[paper_dic['PLOR_CD']]
        
        # F -> 냉동보관
        dic = {'C':'-2℃~10℃ 냉장보관', 'F':'-18℃ 이하 냉동보관'}
        dic = ddict(lambda:'-18℃ 이하 냉동보관', dic)
        paper_dic['STRG_TYPE'] = dic[paper_dic['STRG_TYPE']]
        
        # BOX_WGT -> kg
        paper_dic['BOX_WGT'] = paper_dic['BOX_WGT'] + " kg"
        
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
        # paper_mng.attach(paper_dic["boowi"], "부위명", barcode=False)
        paper_mng.attach(paper_dic["BOX_WGT"], "중량", barcode=False)
        paper_mng.attach(paper_dic["PRINT_DT"], "제조일자", barcode=False)
        paper_mng.attach(paper_dic["EXPIRY_DT"], "유통기한", barcode=False)
        paper_mng.attach(paper_dic["BUTCHERY_NM"], "도축장", barcode=False)
        paper_mng.attach(paper_dic["PLOR_CD"], "원산지", barcode=False)
        paper_mng.attach(paper_dic["STRG_TYPE"], "보관방법", barcode=False)
        options = {'module_width': 0.45, 'module_height': 18}
        paper_mng.attach("L12301305239001", "이력묶음번호", barcode=True, options=options)
        # paper_mng.attach(paper_dic["HIS_NO"], "이력묶음번호", barcode=True, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["BOX_BARCODE"], "바코드1", barcode=True, rotate_num=3, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["BOX_BARCODE"], "바코드2", barcode=True, rotate_num=3, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["BOX_BARCODE"], "바코드3", barcode=True, rotate_num=3, options=options)
        options = {'module_width': 0.4, 'module_height': 10}
        paper_mng.attach(paper_dic["BOX_BARCODE"], "바코드4", barcode=True, rotate_num=3, options=options)
        
        return paper_mng.get_img()
    
    #######################################################################
    # 숫자버튼, 변환버튼, 종료버튼
    
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
        answer = mb.askquestion("종료하기", "종료 할까요?")
        if answer == "no": return
        Thread(target=self.termination, args=(), daemon=True).start()
        
    #######################################################################
    # 바인드 : 조회, 인쇄목록
    
    def update_table(self, event=None):
        # DB 다시 가져오기
        self.table1 = self.table_mng.execute_select("table1", self.cal.get_date())
        logger.info(f"SELECT : {self.cal.get_date()}")
        self.table2 = pd.DataFrame([], columns=self.table2.columns)
        
        # table1 수정
        self.table1[["PROD_QTY", "BOX_IN_CNT"]] = self.table1[["PROD_QTY", "BOX_IN_CNT"]].astype(int)
        dic = ddict(lambda:"대기", {"ORDER":"대기", "RUN":"가동", "END":"종료"})
        self.table1["ORDER_ST"] = list(map(lambda x:dic[x], self.table1["ORDER_ST"]))
        
        # 트리뷰1 청소
        for item_id in self.treeview1.get_children():
            self.treeview1.delete(item_id)
            
        # 트리뷰2 청소
        for item_id in self.treeview2.get_children():
            self.treeview2.delete(item_id)
            
        # 빈 행들 추가하면서 테이블1 열 추가
        for idx in self.table1.index:
            item_id1 = self.treeview1.insert('', 'end')
            self.table1.loc[idx, 'number'] = item_id1
        
        # 트리뷰1 item_id를 df의 인덱스로
        self.table1.index = self.treeview1.get_children()
        
        # 테이블1에서 트리뷰1
        cols = list(self.treeview1['columns'])
        for item_id1 in self.treeview1.get_children():
            self.treeview1.item(item_id1, values=list(self.table1.loc[item_id1, cols]))
        
    def load_print_list(self, event):
        # 선택 검사 ( 그럴리는 없겠지만 )
        temp = self.treeview1.selection()
        if not temp: return
    
        # 트리뷰1에서 지시번호 가져오기
        item_id1 = temp[0]
        order_no = self.table1.loc[item_id1, 'ORDER_NO']
        # row = list(self.treeview1.item(item_id1)['values'])
        # idx = self.treeview1['columns'].index("ORDER_NO")
        # order_no = row[idx]
        
        # DB에서 테이블2
        self.table2 = self.table_mng.execute_select('table2', order_no)
        logger.info(f"SELECT : {order_no} - detail : load_print_list")
        self.table2.rename(columns={'LOT_NO':'WLOT_NO'}, inplace=True)
        
        # 트리뷰2 청소
        for item_id in self.treeview2.get_children():
            self.treeview2.delete(item_id)
            
        # 빈 행들 추가하면서 테이블2 열 추가
        for idx in self.table2.index:
            item_id2 = self.treeview2.insert('', 'end')
            self.table2.loc[idx, 'number'] = item_id2
        
        # 트리뷰2 item_id를 df의 인덱스로
        self.table2.index = self.treeview2.get_children()
        
        # 테이블2에서 트리뷰2
        cols = list(self.treeview2['columns'])
        for item_id2 in self.treeview2.get_children():
            self.treeview2.item(item_id2, values=list(self.table2.loc[item_id2, cols]))
        
    def set_bind(self):
        self.cal.bind("<<DateEntrySelected>>", self.update_table)
        self.treeview1.bind("<<TreeviewSelect>>", self.load_print_list)
    
    #######################################################################
    def __configure(self):
        # 스타일
        style = ttk.Style()
        style.theme_use("default")
        style.configure('my.Treeview', font=('Arial', int(22*self.win_factor), 'bold'), rowheight=50)
        style.configure('my.Treeview.Heading', font=('Arial', int(20*self.win_factor), 'bold'), 
                        background='#B6E2E4', foreground="#000")
        style.layout('Vertical.TScrollbar', [
            ('Vertical.Scrollbar.trough', {'sticky': 'nswe', 'children': [
                ('Vertical.Scrollbar.uparrow', {'side': 'top', 'sticky': 'nswe'}),
                ('Vertical.Scrollbar.downarrow', {'side': 'bottom', 'sticky': 'nswe'}),
                ('Vertical.Scrollbar.thumb', {'sticky': 'nswe', 'unit': 1, 'children': [
                    ('Vertical.Scrollbar.grip', {'sticky': ''})
                    ]})
                ]})
            ])
        
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
        
        # 좌상단테이블프레임 - 버튼
        self.finish_btn = tk.Button(self.top_left_frame, text="지시종료", command=self.finish_order)
        self.finish_btn.place(relx=0.9, rely=0.0, relwidth=0.1, relheight=0.1)
        self.finish_btn['font'] = font.Font(family='Helvetica', size=int(20*self.win_factor), weight='bold')
        self.finish_btn.configure(bg="#333", fg="#fff", activebackground="#fff", activeforeground="#333")
        
        # 좌상단테이블프레임 - 트리뷰
        self.treeview1 = ttk.Treeview(self.top_left_frame, style="my.Treeview")
        self.treeview1['columns'] = self.tree_cols1
        self.treeview1['show'] = 'headings'
        self.treeview1.place(relx=0.0, rely=0.1, relwidth=0.95, relheight=0.9)
        for col, name in zip(self.treeview1['columns'], self.tree_colnames1):
            self.treeview1.heading(col, text=name)
        
        # 좌상단테이블프레임 - 스크롤
        self.scrollbar1 = tk.Scrollbar(self.top_left_frame, orient="vertical", command=self.treeview1.yview)
        self.scrollbar1.place(relx=0.95, rely=0.1, relwidth=0.05, relheight=0.9)
        self.treeview1.configure(yscrollcommand=self.scrollbar1.set)
        
        # test
        # for i in range(100):
        #     aa = self.treeview1.insert("", "end", values=[f"test{i:02d}"]*len(self.tree_cols1))
            
        
        
        # 좌하단테이블프레임
        self.bot_left_frame = tk.Frame(self, bd=10, relief=None, bg=bg_color)
        self.bot_left_frame.place(relx=0.0, rely=0.55, relwidth=0.75, relheight=0.45)
        
        # 좌하단테이블프레임 - 라벨
        self.temp = tk.Label(self.bot_left_frame, text="BOX 바코드 계량 목록", fg="#fff", bg=bg_color, anchor='w')
        self.temp.place(relx=0.0, rely=0.0, relwidth=0.3, relheight=0.1)
        self.temp['font'] = font.Font(family='Helvetica', size=int(30*self.win_factor), weight='bold')
        
        # 좌하단테이블프레임 - 버튼
        self.undo_btn = tk.Button(self.bot_left_frame, text="되돌리기", command=self.undo_append)
        self.undo_btn.place(relx=0.8, rely=0.0, relwidth=0.1, relheight=0.1)
        self.undo_btn['font'] = font.Font(family='Helvetica', size=int(20*self.win_factor), weight='bold')
        self.undo_btn.configure(bg="#333", fg="#fff", activebackground="#fff", activeforeground="#333")
        self.reprint_btn = tk.Button(self.bot_left_frame, text="재인쇄", command=self.resubmit)
        self.reprint_btn.place(relx=0.9, rely=0.0, relwidth=0.1, relheight=0.1)
        self.reprint_btn['font'] = font.Font(family='Helvetica', size=int(20*self.win_factor), weight='bold')
        self.reprint_btn.configure(bg="#333", fg="#fff", activebackground="#fff", activeforeground="#333")
        
        # 좌하단테이블프레임 - 트리뷰
        self.treeview2 = ttk.Treeview(self.bot_left_frame, style="my.Treeview")
        self.treeview2['columns'] = self.tree_cols2
        self.treeview2['show'] = 'headings'
        self.treeview2.place(relx=0.0, rely=0.1, relwidth=0.95, relheight=0.9)
        for col, name in zip(self.treeview2['columns'], self.tree_colnames2):
            self.treeview2.heading(col, text=name)
        self.treeview2.column('BOX_WGT', anchor='e')
        
        # 좌하단테이블프레임 - 스크롤
        self.scrollbar2 = tk.Scrollbar(self.bot_left_frame, orient="vertical", command=self.treeview2.yview)
        self.scrollbar2.place(relx=0.95, rely=0.1, relwidth=0.05, relheight=0.9)
        self.treeview2.configure(yscrollcommand=self.scrollbar2.set)
        
        # test
        # for i in range(100):
        #     aa = self.treeview2.insert("", "end", values=[f"test{i:02d}"]*len(self.tree_cols2))
            
            
            
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
            
        
        
        
        
        