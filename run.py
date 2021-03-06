#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2021/6/26 17:20
@Author  : miaozi
@File    : run.py
@Software: PyCharm
@Desc    :
"""
import argparse
import os
import sys

parser = argparse.ArgumentParser(description='ArgUtils')
parser.add_argument('-t', type=str, default="ss,ssr", help="节点的类型可同时选择多个类型,取值为：ss,ssr,vmess,trojan，默认为ss")
parser.add_argument('-s', type=str, default=None, help="节点的速度任何数字，单个数字选择最低速度，两个数字选择速度区间，默认无限制")
parser.add_argument('-a', type=str, default=None, help="节点的的所在地区可同时选择多个国家，取值为：AT,CN,IN,HK,JP,NL,RU,SG,TW,US...")
parser.add_argument('-e', type=str, default="CN",
                    help="排除某些地区的节点可同时选择多个国家，取值为：AT,CN,IN,HK,JP,NL,RU,SG,TW,US...，默认排除中国的节点")
parser.add_argument('-n', type=int, default=-1, help="要抓取节点的数量，默认无限制")
parser.add_argument('-i', type=int, default=1, help="抓取的结果按ip排序，默认是1,其他表示不排序")
parser.add_argument('-c', type=int, default=0, help="Mac系统上清除ShadowsocksX-NG缓存和取消当前的ss服务配置，与其他参数一起使用时其他参数不生效")
args = parser.parse_args()

cmd = "python app.py"
if args.t:
    cmd += " -t " + args.t
if args.s:
    cmd += " -s " + args.s
if args.a:
    cmd += " -a " + args.a
if args.e:
    cmd += " -e " + args.e
if args.n:
    cmd += " -n " + str(args.n)
if args.i:
    cmd += " -i " + str(args.i)
if args.c:
    cmd += " -c " + str(args.c)

if sys.platform in ['linux', 'darwin']:
    if os.geteuid() != 0:
        # os.system("ulimit -n 10240\nsudo python app.py\n")
        ss_config_path = os.path.join(os.path.expanduser('~/Library/Preferences'),
                                      "com.qiuyuzhou.ShadowsocksX-NG.plist")
        if os.path.exists(ss_config_path):
            if args.c == 1:
                os.system("python app.py -c {0}\n".format(1))
            else:
                os.system("ulimit -n 10240 \n" + cmd)
        else:
            print("你的电脑上没有安装ShadowsocksX-NG，请先安装该软件")
            print("下载地址：https://github.com/shadowsocks/ShadowsocksX-NG/releases/download/v1.9.4/ShadowsocksX-NG.1.9.4.zip")
else:
    os.system(cmd)
