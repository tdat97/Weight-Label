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
        db_info_dic = json.loads(db_info_str)
        self.db_con = pymysql.connect(**db_info_dic, charset='utf8', autocommit=True)
        
    def execute_select(self, detail_dir, *args):
        with open(os.path.join(self.sql_dir_path, detail_dir, "select.txt"), 'r') as f:
            sql = f.read()
        
        sql = sql.format(*args)
        df = pd.read_sql(sql, self.db_con)
        return df
                  
    def execute_update(self, detail_dir, *args):
        with open(os.path.join(self.sql_dir_path, detail_dir, "update.txt"), 'r') as f:
            sql = f.read()
            
        sql = sql.format(*args)
        cur = self.db_con.cursor()
        cur.execute(sql)
        
    def execute_insert(self, detail_dir, *args):
        with open(os.path.join(self.sql_dir_path, detail_dir, "insert.txt"), 'r') as f:
            sql = f.read()
            
        sql = sql.format(*args)
        cur = self.db_con.cursor()
        cur.execute(sql)
        
    def execute_delete(self, detail_dir, *args):
        with open(os.path.join(self.sql_dir_path, detail_dir, "delete.txt"), 'r') as f:
            sql = f.read()
            
        sql = sql.format(*args)
        cur = self.db_con.cursor()
        cur.execute(sql)
  