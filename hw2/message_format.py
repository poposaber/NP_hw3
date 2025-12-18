import json

class MessageFormat:
    def __init__(self, format_dict: dict = {}) -> None:
        """format_dict: key is field name, value is type (str, int, float, bool)"""
        self.format = format_dict

    def to_json(self, *args) -> str:
        result_dict = {}
        args_list = list(args)
        if len(args_list) != len(self.format):
            raise ValueError("Number of arguments does not match format")
        for key, tp in self.format.items():
            value = args_list.pop(0)
            if not isinstance(value, tp):
                raise TypeError(f"Expected {tp} for field '{key}', got {type(value)}")
            result_dict[key] = value
        #print(f"Formatted dict: {result_dict}")
        return json.dumps(result_dict)
    
    def to_arg_list(self, json_str: str) -> list:
        data_dict = json.loads(json_str)
        result_list = []
        for key, tp in self.format.items():
            if key not in data_dict:
                raise KeyError(f"Missing field '{key}' in JSON data")
            value = data_dict[key]
            if not isinstance(value, tp):
                raise TypeError(f"Expected {tp} for field '{key}', got {type(value)}")
            result_list.append(value)
        #print(f"Extracted args: {result_list}")
        return result_list