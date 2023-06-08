from utils import tool

from PIL import ImageFont, ImageDraw, Image
import numpy as np
import json


class PaperManager(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, img_path=None, json_path=None, font_path=None):
        cls = type(self)
        if hasattr(cls, "_init"): return
        cls._init = None
        
        self.origin_img = Image.open(img_path)
        self.label_dic = tool.json2label(json_path)
        self.font_pil = ImageFont.truetype(font_path, size=100)
        self.img = self.origin_img.copy()
        
    def reset(self):
        self.img = self.origin_img.copy()
        
    def attach(self, text, key, barcode=False, rotate_num=0, options=None):
        # 이미지 생성
        if barcode:
            fetch_img = tool.make_barcode_img(text, options=options)
        else:
            fetch_img = tool.make_text_img(text, self.font_pil)
            
        # 이미지 회전
        if rotate_num:
            img = np.array(fetch_img)
            img = np.rot90(img, rotate_num)
            fetch_img = Image.fromarray(img)
        
        # wh 구하기
        xyxy = self.label_dic[key]
        xyxy_wh = xyxy[1] - xyxy[0]
        img_wh = fetch_img.size
        
        # 이미지 resize
        magnf_value = tool.get_fit_magnf(img_wh, xyxy_wh)
        new_img_wh = np.array(img_wh) * magnf_value
        fetch_img = fetch_img.resize(new_img_wh.astype(np.int32))
        
        # print(f"{key} : {fetch_img.size}")
        # 붙이기
        self.img.paste(fetch_img, tuple(map(int, xyxy[0])))
        
    def rotate(self, img_pil, num=1):
        img = np.array(img_pil)
        img = np.rot90(img, num)
        img = Image.fromarray(img)
        return img
        
    def get_img(self):
        return self.img.copy()