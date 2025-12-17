class MessageFormat:
    SEP = '|'
    def __init__(self, name: str, format_list: list = []):
        self.name = name
        self.format_list = format_list
    
    def build(self, arg_list: list = []) -> str:
        if len(arg_list) != len(self.format_list):
            raise ValueError(f"Expected {len(self.format_list)} args, got {len(arg_list)}.")
        
        built = self.name
        
        for format_type, arg in zip(self.format_list, arg_list):
            if type(arg).__name__ != format_type.__name__:
                raise ValueError(f"Expected type {format_type.__name__}, got {type(arg).__name__}")
            if type(arg).__name__ == "str" and MessageFormat.SEP in arg:
                raise ValueError(f"Contains {MessageFormat.SEP}, which is not acceptable")
            built += MessageFormat.SEP + str(arg)
            
        return built
    
    def build_args(self, *args) -> str:
        return self.build(list(args))
    
    def parse(self, message: str) -> list:
        parts = message.split(sep=MessageFormat.SEP)
        if parts[0] != self.name:
            raise ValueError(f"Expected {self.name}, got {parts[0]}.")
        if len(parts) - 1 != len(self.format_list):
            raise ValueError(f"Expected number for parameters of {self.name} is {len(self.format_list)}, got {len(parts) - 1} parameters.")
        parsed = []
        for format_type, part in zip(self.format_list, parts[1:]):
            try:
                parsed.append(format_type(part))
            except Exception:
                raise ValueError(f"failed to parse {part} as {format_type.__name__}.")
        return parsed
