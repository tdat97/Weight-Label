import pandas as pd
import json
import time
import os

import warnings
warnings.filterwarnings('ignore')


class TableManager():
    def __init__(self, db_con, sql_dir_path, nodb_path, add_cols=[], add_init=[]):
        assert len(add_cols) == len(add_init)
        self.add_cols = add_cols
        self.add_init = add_init
        self.db_con = db_con
        self.nodb_path = nodb_path
        
        # sql 가져오기
        with open(os.path.join(sql_dir_path, "select.txt"), 'r') as f:
            self.select_sql = f.read()
        with open(os.path.join(sql_dir_path, "insert.txt"), 'r') as f:
            self.insert_sql = f.read()
        with open(os.path.join(sql_dir_path, "update.txt"), 'r') as f:
            self.update_sql = f.read()
        
        # 테이블
        self.df = None
        
    def excute_select(self, date):
        # 이전 df 저장
        old_df = self.df
        
        
        # DB 읽기
        sql = self.select_sql.format(date)
        if self.db_con is None:
            self.df = pd.read_csv(self.nodb_path, encoding='cp949')
        else:
            self.df = pd.read_sql(sql, self.db_con)
            
        # 미분류 행추가
        # temp = pd.DataFrame([['NONE', '']], columns=['ITEM_CD', 'ITEM_NM'])
        # self.df = pd.concat([df, temp], axis=0, ignore_index=True)
                
    
        # 열추가
        for col, v in zip(self.add_cols, self.add_init):
            self.df[col] = v
        if old_df is None or not self.add_cols:
            return
        
        # 열 옮기기
        for row in old_df.iloc:
            # 첫번째 열이 key라 가정
            idxs = self.df[self.df.iloc[:,0] == row[0]].index
            if len(idxs):
                idx = idxs[0]
                self.df.loc[idx] = row
                
    def excute_update(self, col, formula, order_no):
        if self.db_con is None: return
        sql = self.update_sql.format(col, formula, order_no)
        cur = self.db_con.cursor()
        cur.execute(sql)