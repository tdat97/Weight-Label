

class CodeMaker():
    ai_dic = {'sscc'	:"00{sscc:0>18}", # 물류단위식별일련번호(SSCC)
              'gtin'	:"01{gtin:0>14}", # 상품식별코드(GTIN)
              'luapic'	:"02{luapic:0>14}", # 물류단위 입수 상품식별코드
              'lot'		:"10{lot:0>{len_lot}}", # 배치/로트번호
              'pdate'	:"11{pdate:0>6}", # 생산일자(YYMMDD)
              'odate'	:"15{odate:0>6}", # 최적유통일자(YYMMDD)
              'sdate'	:"16{sdate:0>6}", # 판매기한(YYMMDD)
              'edate'	:"17{edate:0>6}", # 유통기한(YYMMDD)
              'serial'	:"21{serial:0>{len_serial}}", # 일련번호
              'weight'	:"310{pos}{weight:0>6}", # 순중량 (킬로그램)
              'pqoblu'	:"37{pqoblu:0>{len_pqoblu}}", # 물류 단위 입수상품 수량
              'pay'		:"390{pay:0>{len_pay}}", # 지불금액
              'ginc'	:"401{ginc:0>{len_ginc}}", # 국제위탁화물식별번호(GINC)
              'post'	:"420{post:0>{len_post}}", # 배송지(납품지) 우편번호
             }
    
    @classmethod
    def get_gtin(cls, nation='880', company='001000', product='001'): # 표준형 상품식별코드(GTIN-13)
        gtin_code = f"{nation}{company:0>6}{product:0>3}"
        digit = cls.get_check_digit(gtin_code)
        return gtin_code + digit
        
    @classmethod
    def get_check_digit(cls, code, system="GTIN-13"):
        if system == "GTIN-13":
            assert len(code) in [12, 13]
            code = code[:-1] if len(code) == 13 else code
            
        else:
            raise Exception("다른 체계는 미구현")
            
        tot = 0
        for i, v in enumerate(code[::-1]):
            tot += int(v)*3 if i%2 == 0 else int(v)
        return str(-tot%10)
    
    @classmethod
    def combi_with_ai(cls, keys, data_dic):
        format_str = ''.join([cls.ai_dic[key] for key in keys])
        code = format_str.format(**data_dic)
        return code