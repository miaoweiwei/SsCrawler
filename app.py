﻿#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2021/6/26 17:20
@Author  : miaozi
@File    : app.py
@Software: PyCharm
@Desc    : 
"""
import argparse
import json
import multiprocessing
import os
import socket
import ssl
import sys
import time
import uuid
from multiprocessing import Process, Queue, set_start_method
from urllib.parse import urlparse

import biplist
import gevent
import psutil
from gevent import monkey
import crawler.ip_crawler as ip_crawler

# 解决SSL问题
ssl._create_default_https_context = ssl._create_unverified_context

from crawler import UserAgentManager, Shadowsocks, SspoolCrawler, ShadowsocksEncoder

# socket.setdefaulttimeout(1)  # 这里对整个socket层设置超时时间。后续文件中如果再使用到socket，不必再设置

method_set_shadowsocks = {"aes-256-gcm", "aes-192-gcm", "aes-128-gcm", "chacha20-ietf-poly1305",
                          "xchacha20-ietf-poly1305"}
method_set_shadowsocks_x = {"aes-128-gcm", "aes-192-gcm", "aes-256-gcm", "aes-128-cfb", "aes-192-cfb",
                            "aes-256-cfb", "aes-128-ctr", "aes-192-ctr", "aes-256-ctr", "camellia-128-cfb",
                            "camellia-192-cfb", "camellia-256-cfb", "bf-cfb", "chacha20-ietf-poly1305",
                            "xchacha20-ietf-poly1305", "salsa20", "chacha20", "chacha20-ietf", "rc4-md5"}

connect_retry_count = 5
connect_ratio = 0.6
connect_timeout = 0.3


class CrawlerUrl(object):
    def __init__(self, url, types={}, speed=None, area={}, exclude_area={}, is_proxy=False):
        self.base_url = url
        self.types = types
        self.speed = speed
        self.area = area
        self.exclude_area = exclude_area
        self.is_proxy = is_proxy

    @property
    def url(self):
        url_temp = ""
        if len(self.types) > 0:
            url_temp = url_temp + "type=" + ",".join(self.types)
        if self.speed is not None:
            url_temp += "{0}speed={1}".format(("&" if len(url_temp) > 0 else ""), self.speed)
        if self.area is not None and len(self.area) > 0:
            url_temp += "{0}c={1}".format(("&" if len(url_temp) > 0 else ""), ",".join(self.area))
        if self.exclude_area is not None and len(self.exclude_area) > 0:
            url_temp += "{0}nc={1}".format(("&" if len(url_temp) > 0 else ""), ",".join(self.exclude_area))

        return self.base_url if len(url_temp) <= 0 else "{0}?{1}".format(self.base_url, url_temp)

    @url.setter
    def url(self, value):
        self.base_url = value


def check_server(aq, ss):
    """检测 Shadowsocks 服务是否可以正常访问
        函数返回True，表示端口是能连接的；函数返回False，表示端口是不能连接的
    """
    if sys.platform in ['win32', 'cygwin'] and ss.method not in method_set_shadowsocks:
        print("加密方式不支持 ", ss)
        return
    if sys.platform in ['linux', 'darwin'] and ss.method not in method_set_shadowsocks_x:
        print("加密方式不支持 ", ss)
        return
    address = (ss.server, int(ss.server_port))
    socket_types = socket.getaddrinfo(*address)
    # 判断ip是否在大陆，如果是就返回
    if ip_crawler.ip_in_cn(socket_types[-1][-1][0]):
        print("服务在中国大陆忽略 ", ss)
        return
    # sock = socket.socket(*socket_types[-1][:2])
    connect_count = 0
    for i in range(connect_retry_count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(connect_timeout)  # 设置超时时间
        status = sock.connect_ex(address)
        if status == 0:
            connect_count += 1
        sock.close()
    if connect_count / connect_retry_count > connect_ratio:
        aq.put(ss)
    else:
        print("连接不成功 ", ss)


def collect(aq, ss_data):
    while True:
        ss = aq.get(True)
        ss_data.append(ss)
        print("可用 {0}".format(str(ss)))


def proc_ss_from_queue(sss, aq):
    """从队列里读取 Shadowsocks 账户数据然后使用协成进行对 Shadowsocks 服务进行判断是否可用
        然后把可用的Shadowsocks账号信息存到 aq 这个队里去
    """
    greenlets = [gevent.spawn(check_server, aq, ss) for ss in sss]
    gevent.joinall(greenlets)  # 等待所有协程结束


def crawl_ss(crawler, aq):
    cur_proc = multiprocessing.current_process()
    print("进程 {0} 启动, url: {1} 开始抓取配置...".format(cur_proc.name, crawler.url))
    data = crawler.crawl()
    print("进程 {0} 共抓取数据 {1} 条".format(cur_proc.name, len(data)))
    ss_check_count = 1000  # 指定每一个进程最多有多少个协成
    if sys.platform in ['linux', 'darwin']:
        ss_check_count = 2048  # 如果是Linux和mac环境就指定每一个进程最多可以有2048个协程
    if data:
        if len(data) <= ss_check_count:
            proc_ss_from_queue(data, aq)
        else:
            pro_list = []
            for i in range(0, len(data), ss_check_count):
                pro = Process(target=proc_ss_from_queue, args=(data[i:i + ss_check_count], aq))
                pro_list.append(pro)
                pro.start()
            for pro in pro_list:
                pro.join()


def set_ss_config(sss):
    ss_proc = None
    for proc in psutil.process_iter():
        if proc.name() == 'Shadowsocks.exe':
            ss_proc = proc
            break
    if not ss_proc:
        wait_num = 0
        print("Shadowsocks 程序没有启动，请启动 Shadowsocks 程序")
        while True:
            for proc in psutil.process_iter():
                if proc.name() == 'Shadowsocks.exe':
                    ss_proc = proc
                    break
            print("\r正在检测 Shadowsocks 程序 {0}".format(wait_num % 5 * "."), end='')
            wait_num += 1
            time.sleep(0.5)
            if ss_proc:
                break
    print("\r\n 捕获到 Shadowsocks 程序")
    cmdline = ss_proc.exe()  # 获取进程的路径
    ss_proc.terminate()  # 杀掉 Shadowsocks 程序

    ss_path = os.path.dirname(cmdline)
    ss_config_path = os.path.join(ss_path, 'gui-config.json')

    # 使用 r+ 读写文件 先读出文件的内容，然后修改 ss 配置，然后在情况原来的内容，然后在把修改后的内容写回
    with open(ss_config_path, 'r+', encoding='utf-8') as f:
        # 读取源文件
        ss_config = json.load(f)
        # 修改 Shadowsocks 账号配置
        ss_config['configs'] = sss
        # 服务模式选择，我们这里选择 高可用
        # 负载均衡
        # ss_config['strategy'] = "com.shadowsocks.strategy.balancing"
        # 高可用
        ss_config['strategy'] = "com.shadowsocks.strategy.ha"
        # 高可用 或者是 负载均衡时 服务索引都要设置成 -1
        ss_config['index'] = -1
        ss_config["localPort"] = 1088
        # 把文件指针回到开始的位置
        f.seek(0, 0)
        # 清空文件内容
        f.truncate()
        # 写回, sort_keys 设置格式化， indent 缩进2个字符
        json.dump(ss_config, f, sort_keys=True, indent=2, cls=ShadowsocksEncoder)
    #  重新启动 Shadowsocks 程序
    os.popen(cmdline)
    print("Shadowsocks 程序 配置成功")


def remove_tree(path):
    """ 递归的删除文件夹及其内部的文件
    Args:
        path: 文件夹/文件路径
    """
    if os.path.isfile(path):
        os.remove(path)
    else:
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(path)


def set_ss_config_by_mac(sss=None, only_clear_cache=False):
    def ss2dic(ss: Shadowsocks):
        return {'Method': ss.method, 'Plugin': '', 'Remark': ss.remarks, 'Id': str(uuid.uuid1()).upper(),
                'ServerPort': ss.server_port, 'Password': ss.password, 'ServerHost': ss.server, 'PluginOptions': ''}

    ss_config_path = os.path.join(os.path.expanduser('~/Library/Preferences'), "com.qiuyuzhou.ShadowsocksX-NG.plist")
    ss_local_config_path = os.path.join(os.path.expanduser("~/Library/Application Support/ShadowsocksX-NG"),
                                        "ss-local-config.json")
    # 缓存地址
    ss_config_caches_path = os.path.join(os.path.expanduser("~/Library/Caches/com.qiuyuzhou.ShadowsocksX-NG"))

    # 查找 ShadowsocksX-NG 程序是否已经启动
    shadowsocks_x_path = ""
    for proc in psutil.process_iter():
        # 不能是僵尸进程
        if proc.status() != 'zombie' and proc.name() == 'ShadowsocksX-NG':
            # 已经启动就记录下程序的启动路径，然后关闭程序，等待更新完成配置文件后在启动
            shadowsocks_x_path = proc.exe()
            print("关闭 ", shadowsocks_x_path, " 程序")
            proc.terminate()
            break

    linux_sss = [ss2dic(ss) for ss in sss] if only_clear_cache is False else []
    ss_config = None
    if os.path.exists(ss_config_path) and os.path.getsize(ss_config_path) > 0:
        ss_config = biplist.readPlist(ss_config_path)
    else:
        # 文件不存在
        pass
    if ss_config is None:
        print("请先修改一下ShadowsocksX-NG的配置，然后在运行程序")
        exit(0)
    ss_config["ServerProfiles"] = linux_sss
    biplist.writePlist(ss_config, ss_config_path)
    print("更新ShadowsocksX-NG配置 ", ss_config_path, " 成功...")

    if os.path.exists(ss_local_config_path):
        remove_tree(ss_local_config_path)
        print("删除ShadowsocksX-NG当前配置 ", ss_local_config_path, " 成功...")
    if os.path.exists(ss_config_caches_path):
        remove_tree(ss_config_caches_path)
        print("删除ShadowsocksX-NG缓存 ", ss_config_caches_path, " 成功...")

    if shadowsocks_x_path and only_clear_cache is False:
        for i in range(1, 11):
            print("等待启动中" + "." * i)
            time.sleep(1)
        os.popen(shadowsocks_x_path)
        print("ShadowsocksX-NG重新启动")
    else:
        print("请重启电脑以便清除ShadowsocksX-NG在内存中的记录")


def build_url(url_proxy_dic, types={}, speed=None, area={}, exclude_area={}):
    crawler_urls = []
    if not url_proxy_dic:
        return crawler_urls
    for base_url, is_proxy in url_proxy_dic.items():
        url = CrawlerUrl(base_url, types=types, speed=speed, area=area, exclude_area=exclude_area, is_proxy=is_proxy)
        crawler_urls.append(url)
    return crawler_urls


def create_ss_pool_crawler_process(ua_manager, ssq, crawler_urls):
    crawlers = []
    if not crawler_urls:
        return crawlers
    for crawler_url in crawler_urls:
        crawler = SspoolCrawler(ua_manager, url=crawler_url.url, types=crawler_url.types, country=crawler_url.area,
                                exclude_country=crawler_url.exclude_area, is_proxy=crawler_url.is_proxy)
        crawler_pro = Process(target=crawl_ss, args=(crawler, ssq))
        crawler_pro.name = urlparse(crawler.url).netloc  # 使用域名来做为的名字
        crawlers.append(crawler_pro)
    return crawlers


def main(types='', speed='', ss_count=-1, area='', exclude_area='', ip_sort=1):
    """ 主函数
    @param types: 节点的类型
    @param speed: 选择 节点 的速度
    @param ss_count: 选择 节点 的数量
    @param area: 选择 节点 的地区
    @param exclude_area: 要排除的地区
    @param ip_sort: 抓取的结果按ip排序，默认是
    """
    # python多进程间用Queue通信时，如果子进程操作Queue满了或者内容比较大的情况下，
    # 该子进程会阻塞等待取走Queue内容(如果Queue数据量比较少，不会等待)，如果调用join，主进程将处于等待，等待子进程结束，造成死锁
    # 解决方式：在调用join前，及时把Queue的数据取出，而且Queue.get需要在join前

    types = set(types.split(',') if types is not None and len(types) > 0 else [])
    area = set(area.split(',') if area is not None and len(area) > 0 else [])
    exclude_area = set(exclude_area.split(',') if exclude_area is not None and len(exclude_area) > 0 else [])

    exclude_area.add("CN")  # 把国内的节点排除掉
    print("启动抓取程序,要抓取节点的类型：{0}，速度：{1}，节点的个数：{2}".format(types, speed, ss_count))

    # 先去加载ip文件
    if ip_crawler.check_ip_file_overdue():
        print("ip文件已经过期，正在重新下载")
        ip_crawler.download_ip()

    ip_crawler.load_ip_file()
    print("ip文件加载完成！")

    start_time = time.time()
    uaManager = UserAgentManager()
    available_data_queue = Queue()

    url_proxy_dic = {
        "https://fq.lonxin.net/clash/proxies": False,
        "https://free.jingfu.cf/clash/proxies": False,
        "https://free.dswang.ga/clash/proxies": False,
        # "https://ss.dswang.ga:8443/clash/proxies": False, # 同上一个节点池
        "https://proxies.bihai.cf/clash/proxies": False,
        "https://sspool.herokuapp.com/clash/proxies": False,
        "https://free886.herokuapp.com/clash/proxies": False,
        "http://wxshi.top:9090/clash/proxies": False,
        "http://39.106.12.141:8081/clash/proxies": False,
        "https://proxypoolss.fly.dev/clash/proxies": False,
        "https://raw.githubusercontent.com/adiwzx/freenode/main/adispeed.yml": False,
        "https://raw.githubusercontent.com/AzadNetCH/Clash/main/AzadNet.yml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0207/clash.yaml": False,
        ## "https://git.ddns.tokyo/du5/free/master/file/0503/clash.yaml": False, # 不可用
        "https://raw.githubusercontent.com/du5/free/master/file/0407/clash.yaml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0407/clash2.yaml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0404/clash.yaml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0312/clash.yaml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0307/clash.yaml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0909/Clash.yaml": False,
        "https://raw.githubusercontent.com/du5/free/master/file/0906/surge.conf": False,  # 返回值是yaml类型的列表
    }
    crawler_urls = build_url(url_proxy_dic, types=types, speed=speed, area=area, exclude_area=exclude_area)
    crawlers = create_ss_pool_crawler_process(uaManager, available_data_queue, crawler_urls)
    monkey.patch_all()  # 实现了协程任务的调度
    # 启动爬虫进程
    for crawler in crawlers:
        crawler.start()

    time.sleep(1)
    # Shadowsocks 过滤或可用的账号列表, 在主线程中进行收集
    ss_set = set()
    flag = True
    while flag:
        while not available_data_queue.empty():
            try:
                ss = available_data_queue.get(timeout=1)
                print("可用 {0}".format(str(ss)))
                ss_set.add(ss)
                if 0 < ss_count == len(ss_set):
                    for crawler in crawlers:
                        if crawler.is_alive():
                            crawler.terminate()
            except Exception as ex:
                print("队列超时", ex)
                break

        for crawler in crawlers:
            if crawler.is_alive():
                print("进程 {0} 存活".format(crawler.name))
        if any([crawler.is_alive() for crawler in crawlers]):
            time.sleep(1)
        else:
            time.sleep(3)
            if available_data_queue.empty():
                break

    print("共有", len(ss_set), "个服务可以使用，准备配置 Shadowsocks")
    ss_list = list(ss_set)
    if ip_sort == 1:  # 按照ip排序
        ss_list.sort(key=lambda ss: ss.server)
    if sys.platform in ['win32', 'cygwin']:
        set_ss_config(ss_list)
    elif sys.platform in ['linux', 'darwin']:
        set_ss_config_by_mac(sss=ss_list)
    print("完成, 总耗时：{0} 秒".format(time.time() - start_time))


if __name__ == '__main__':
    # 设置多进程的启动方式
    set_start_method("spawn")
    # 使用IDE调试用这两句代码
    # main(types="ss,ssr", speed='50', ss_count=200, area=None, exclude_area="CN", ip_sort=1)
    # exit(0)
    # 正常运行注释上面两句代码
    parser = argparse.ArgumentParser(description='ArgUtils')
    parser.add_argument('-t', type=str, default="ss,ssr", help="节点的类型可同时选择多个类型,取值为：ss,ssr,vmess,trojan，默认为ss")
    parser.add_argument('-s', type=str, default=None, help="节点的速度任何数字，单个数字选择最低速度，两个数字选择速度区间，默认无限制")
    parser.add_argument('-a', type=str, default=None, help="节点的的所在地区可同时选择多个国家，取值为：AT,CN,IN,HK,JP,NL,RU,SG,TW,US...")
    parser.add_argument('-e', type=str, default="CN",
                        help="排除某些地区的节点可同时选择多个国家，取值为：AT,CN,IN,HK,JP,NL,RU,SG,TW,US...，默认排除中国的节点")
    parser.add_argument('-n', type=int, default=-1, help="要抓取节点的数量，默认无限制")
    parser.add_argument('-i', type=int, default=0, help="抓取的结果按ip排序，默认是")
    parser.add_argument('-c', type=int, default=0, help="Mac系统上清除ShadowsocksX-NG缓存和取消当前的ss服务配置，与其他参数一起使用时其他参数不生效")
    args = parser.parse_args()

    if args.c == 1:
        set_ss_config_by_mac(only_clear_cache=True)
        exit(0)

    type_list = ["ss", "ssr", "vmess", "trojan"]
    types = args.t.split(",")
    for t in types:
        if t not in type_list:
            raise Exception("不支持{0}类型的节点抓取".format(t))

    speed = args.s if args.s != "None" else None
    if speed is not None:
        try:
            if speed.count(",") > 1:
                raise Exception("速度参数 {0} 不合法".format(speed))
            elif speed.count(",") == 1:
                speeds = speed.split(",")
                if int(speeds[0]) > int(speeds[1]):
                    raise Exception("速度参数 {0} 不合法".format(speed))
            else:
                int(speed)
        except Exception as ex:
            raise Exception("速度参数 {0} 不合法".format(speed))
    main(types=args.t, speed=speed, ss_count=args.n, area=args.a, exclude_area=args.e, ip_sort=args.i)
