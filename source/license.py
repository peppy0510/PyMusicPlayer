# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import json
import random
import socket
import urllib
from utilities import string2md5
# import hashlib
# import urllib2
# from utilities import get_hostname
# from utilities import get_macaddress
# from utilities import get_external_ip


def get_table(num=True, upper=True, lower=True):
    table = list()
    if num:
        for i in range(48, 58):
            table.append(str(unichr(i)))
    if upper:
        for i in range(65, 91):
            table.append(str(unichr(i)))
    if lower:
        for i in range(97, 123):
            table.append(str(unichr(i)))
    return table


def string2longhex(seed, length):
    code = string2md5(seed)
    longhex = list()
    for i in range(length / 32 + 1):
        code = string2md5(code)
        longhex.append(code)
    return ''.join(longhex)[:length]


def string2longdec(seed, length):
    longhex = string2longhex(seed, length)
    longdec = str(int(longhex, 16))
    return longdec[:length]


def rotate_table(table, seed):
    table_length = len(table)  # 62
    order = int(string2longdec(seed, 64)) % table_length
    table = table[order:] + table[:order]
    table = ''.join(table)
    return table


def get_rotated_table(seed, num=True, upper=True, lower=True):
    table = get_table(num=num, upper=upper, lower=lower)
    return rotate_table(table, seed)


def generate_code(seed, length=64, num=True, upper=True, lower=True):
    longdec = string2longdec(seed, length * 4)
    table = get_rotated_table(seed, num=num, upper=upper, lower=lower)
    table_length = len(table)
    y = list()
    for i in range(0, len(longdec), 4):
        x = int(longdec[i:i + 4]) % table_length
        y.append(table[x])
    return ''.join(y)


def generate_license_code(seed, length=64):
    return generate_code(seed, length=64)


def is_valid_license(seed, code):
    if code != generate_license_code(seed):
        return False
    return True


def generate_random_code(length, num=True, upper=True, lower=True):
    table = ''.join(get_table(num=num, upper=upper, lower=lower))
    code = [random.choice(table) for v in range(length)]
    return ''.join(code)


def generate_random_seeded_code(seed, length, num=True, upper=True, lower=True):
    table = ''.join(get_rotated_table(seed, num=num, upper=upper, lower=lower))
    code = [random.choice(table) for v in range(length)]
    return ''.join(code)


def request_code(email, publickey, product, device, url):
    socket.setdefaulttimeout(5)
    values = {
        'email': email,
        'publickey': publickey,
        'product': product,
        'device': device}
    try:
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        result = response.read()
        result = json.loads(result)
    except:
        result = None
    return result


def generate_secretkey(email, publickey, product, macaddress):
    seed = ''.join((email, publickey, product, macaddress))
    return generate_license_code(seed)


if __name__ == '__main__':
    pass
