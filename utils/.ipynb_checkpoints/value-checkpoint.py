class ValueControl():
    def __init__(self, dtype=float):
        self.dtype = dtype
        self.real_value = dtype(0)
        self.value_text = '0'
        
    def input_cmd(self, cmd):
        assert len(cmd) == 1
        
        # 숫자 체크
        if cmd.isdigit():
            if self.real_value == 0: self.value_text = ''
            self.value_text += cmd
            self.real_value = self.dtype(self.value_text)
        elif cmd == '.':
            if self.real_value == 0 or '.' in self.value_text: return
            self.value_text += cmd
        else:
            self.value_text = self.value_text[:-1]
            if self.value_text == '':
                self.value_text = '0'
            self.real_value = self.dtype(self.value_text)
        
        # 길이체크
        if len(self.value_text) > 6:
            self.value_text = self.value_text[:-1]
            self.real_value = self.dtype(self.value_text)
    
    def set_value(self, value):
        assert type(value) == str
        assert len(value) > 0
        assert self.dtype == float or not '.' in value, "int인데 점(.)이 있음"
        assert '.' != value[0]
        
        self.value_text = value
        self.real_value = self.dtype(value)
        
    def print_value(self):
        print('value_text :', self.value_text)
        print('real_value :', self.real_value)
        
                