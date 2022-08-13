#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2022/6/9 12:11
@Author  : miao
@File    : ip_crawler.py
@Software: PyCharm
@Desc    :
定期获取Apnic分配给中国的IP网段 列表
Apnic是全球5个地区级的Internet注册机构（RIR）之一，负责亚太地区的以下一些事务：
（1）分配IPv4和IPv6地址空间，AS号
（2）为亚太地区维护Whois数据库
（3）反向DNS指派
（4）在全球范围内作为亚太地区的Internet社区的代表
ip获取地址 http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest
"""
import datetime
import os
import socket
from urllib import request

ip_url = "http://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest"
# 使用这个字符串为处理后的ip文件名字的前缀
ip_file_name = "cn_ip.txt"

# ip 列表用于检查ip使用存在与ip_list中即是否在中国
ip_list_cache = None


def get_ip_file_path():
    project_path = os.path.abspath(os.path.dirname(__file__)).split('/SsCrawler')[0]
    return "{0}/SsCrawler/config/{1}".format(project_path, ip_file_name)


def download_ip():
    ip_f = request.urlopen(ip_url)
    with open(get_ip_file_path(), 'w') as f:
        # 在首行加入更新时间用于检查ip文件是否过期
        f.writelines(["{0}\n".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))])
        data = ip_f.read().decode("utf-8").split("\n")

        ip_list = [ip_temp.split('|')[3:5] for ip_temp in data if valid_ip_in_cn(ip_temp)]
        ip_list = ["{0}/{1}\n".format(ip2long(ip), count) for ip, count in ip_list]
        f.writelines(ip_list, )
    print("ip文件更新完成！")


def valid_ip_in_cn(ip):
    if 'apnic|CN|ipv4|' in ip:
        return valid_ip(ip.split('|')[3])
    return False


def valid_ip(ip):
    try:
        socket.inet_aton(ip)
        return True
    except:
        return False


def ip2long(ip):
    if ip == 0:
        return 0
    check = valid_ip(ip)
    if check is False:
        return 0
    tmp = ip.split(".")
    return (int(tmp[0]) << 24) + (int(tmp[1]) << 16) + (int(tmp[2]) << 8) + int(tmp[3]);


def check_ip_file_overdue(limit=7):
    """ 判断ip文件是否过期
    @param limit: 有效时间，单位天
    @return:是否过期
    """
    if os.path.exists(get_ip_file_path()):
        with open(get_ip_file_path(), 'r') as f:
            old_datetime = datetime.datetime.fromisoformat(f.readlines(1)[0].strip()).timestamp()
            now_datetime = datetime.datetime.now().timestamp()
            return old_datetime + 60 * 60 * 24 * 7 < now_datetime
    return True


def load_ip_file():
    # 需要去加载ip文件
    global ip_list_cache
    if os.path.exists(get_ip_file_path()):
        with open(get_ip_file_path(), 'r') as f:
            data = f.read()
            ip_list_cache = [(int(info.split("/")[0]), int(info.split("/")[1])) for info in data.split("\n")[1:-1]]


def ip_in_cn(ip):
    if ip_list_cache is None:
        raise Exception("请先加载ip文件")
    ip_num = ip2long(ip)
    for ip_num_temp, count in ip_list_cache:
        if ip_num_temp <= ip_num < ip_num_temp + count:
            return True
        elif ip_num < ip_num_temp:
            return False
    return False


if __name__ == '__main__':
    # download_ip()
    aa = check_ip_file_overdue()
    print(aa)
    load_ip_file()
    in_cn = ip_in_cn("66.249.66.12")
    print(in_cn)
