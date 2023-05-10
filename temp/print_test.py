from PIL import Image, ImageWin
import win32ui
import win32print

# 이미지 파일 열기
img = Image.open("white.png")

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
