from barcode.writer import ImageWriter
import barcode
import io
from PIL import Image
def make_barcode_img(code, kind='gs1_128', options=None):
    assert type(code) is str
    
    # 바코드 생성
    bar = barcode.get(kind, code, writer=ImageWriter())
    options = {'module_width': 0.4, 'module_height': 10} if options is None else options
    barcode_image = bar.render(options)
    
    return barcode_image


from PIL import ImageFont, ImageDraw, Image
def make_text_img(text, font_pil, margin=10):
    # 글씨 이미지 wh 구하기
    font_wh = [int(font_pil.getlength(text)), font_pil.size]
    font_wh[0] += margin*2
    font_wh[1] += margin*2

    # 빈 이미지 생성
    img = Image.new('RGB', font_wh, (255,255,255))

    # 글씨 그리기
    draw = ImageDraw.Draw(img)
    draw.text((margin, margin), text, font=font_pil, fill='#000')

    return img


def get_fit_magnf(wh, target_wh):
    assert len(wh) == len(target_wh) == 2
    
    w, h = wh
    tw, th = target_wh
    magnf_value = min(tw/w, th/h)
    return magnf_value


import win32ui, win32print
from PIL import ImageWin
def print_file(img):
    # 프린터 선택
    printer_name = win32print.GetDefaultPrinter()

    # 인쇄하기
    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer_name)
    dc.StartDoc("image")
    dc.StartPage()
    bmp = ImageWin.Dib(img)
    bmp.draw(dc.GetHandleOutput(), (0, 0, img.size[0], img.size[1]))
    dc.EndPage()
    dc.EndDoc()
    dc.DeleteDC()
    
    
import numpy as np
import json
def json2label(path, return_dic=True): # json 경로
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    labels = [shape["label"] for shape in data["shapes"]]
    points = np.float32([shape["points"] for shape in data["shapes"]]) # (n, 2?, 2)
    if return_dic:
        return dict(zip(labels, points))
    else:
        return labels, points