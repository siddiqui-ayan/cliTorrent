import pprint
# Wrote my own bdecode and encode library because I don't have a life

def bdecode(data, index=0):
    """A simple Bencode decoding function"""

    # deecoding integer type
    if data[index: index+1] == b'i':
        end = data.index(b'e', index) # search for value 'e' starting from 'index'
        number = int(data[index+1:end])
        return number, end + 1
    
    # decoding string type
    elif data[index:index+1].isdigit():
        colon = data.index(b':', index)
        length = int(data[index:colon])
        end = colon + 1 + length
        string = data[colon+1:end]
        return string, end
    
    # decoding dictionary type
    elif data[index:index+1] == b'd':
        index = index + 1
        result = {}
        while data[index:index+1] != b'e':
            key, index = bdecode(data, index)
            value, index = bdecode(data, index)
            result[key] = value

        return result, index + 1

    # decoding list types
    elif data[index:index+1] == b'l':
        index += 1
        result = []
        while data[index:index+1] != b'e':
            item, index = bdecode(data,index)
            result.append(item)
            
        return result, index + 1


def bencode(data):
    "A simple bencode encoding function"
    if isinstance(data, int):
        return b'i' + str(data).encode() + b'e'

    elif isinstance(data, bytes):
        return str(len(data)).encode() + b':' + data

    elif isinstance(data, str):
        data = data.encode()
        return str(len(data)).encode() + b':' + data

    elif isinstance(data, list):
        result = b'l'
        for item in data:
            result += bencode(item)
        result += b'e'
        return result

    elif isinstance(data, dict):
        result = b'd'
        for key in sorted(data.keys()):
            result += bencode(key)
            result += bencode(data[key])
        result += b'e'
        return result


# with open('./examples/test.torrent', 'rb') as f:
#     raw = f.read()
#     decoded, _ = bdecode(raw)
#     pprint.pprint(decoded[b'info'].keys())
#     pprint.pprint(decoded.keys())
#     print(raw == bencode(decoded))
    
