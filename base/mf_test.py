from message_format import MessageFormat
# from protocols.formats import Formats

mf = MessageFormat({
    'a': str, 
    'b': dict
})

jstr = mf.to_json("this", {"2": 7, 'real': True, 'fake': 1.4352343, 'another': {'haha': 234}})
p1, p2 = mf.to_arg_list(jstr)

print(p1, p2)
print(type(p2['another']['haha']))