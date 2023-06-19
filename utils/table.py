from utils.crypto import glance
import pandas as pd
import pymysql
import json
import os

import warnings
warnings.filterwarnings('ignore')

class TableManager():
    def __init__(self, sql_dir_path, db_info_path, key_path=None):
        self.sql_dir_path = sql_dir_path
        db_info_str = glance(db_info_path, key_path)
        self.db_info_dic = json.loads(db_info_str)
        self.db_con = pymysql.connect(**self.db_info_dic, charset='utf8', autocommit=True, connect_timeout=30)
        self.sql_cache = {}
        
    def execute(self, mode, detail_dir, *args):
        assert mode in ["select", "update", "insert", "delete"]
        
        # sql 읽기
        sql_path = os.path.join(self.sql_dir_path, detail_dir, f"{mode}.txt")
        key_path = os.path.join(self.sql_dir_path, detail_dir, f"{mode}_key.txt")
        if sql_path in self.sql_cache:
            sql = self.sql_cache[sql_path]
        else:
            sql = glance(sql_path, key_path)
            self.sql_cache[sql_path] = sql
        
        # sql 포맷팅
        sql = sql.format(*args)
        
        # 연결 테스트 / 재연결
        try:
            cur = self.db_con.cursor()
            cur.execute('SELECT 1')
        except:
            if self.db_con: self.db_con.close()
            self.db_con = pymysql.connect(**self.db_info_dic, charset='utf8', autocommit=True)
            
        # sql 쿼리 실행
        if mode == "select":
            df = pd.read_sql(sql, self.db_con)
            return df
        else:
            cur = self.db_con.cursor()
            cur.execute(sql)