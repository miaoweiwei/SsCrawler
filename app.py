#!/usr/bin/env python
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
from multiprocessing import Process, Queue
from typing import Any
from urllib.parse import urlparse

import gevent
import psutil
from gevent import monkey
from gevent.subprocess import Popen, PIPE

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


class LinuxShadowsocks(object):
    def __init__(self, plugin, remark, id, method, port, password, host, pluginOpt):
        self.Plugin = plugin
        self.Remark = remark
        self.Id = id
        self.Method = method
        self.ServerPort = port
        self.Password = password
        self.ServerHost = host
        self.PluginOptions = pluginOpt


class LinuxShadowsocksEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, LinuxShadowsocks):
            return o.__dict__
        return json.JSONEncoder.default(self, o)


class CrawlerUrl(object):
    def __init__(self, url, types=set(), speed=None, area=set(), exclude_area=set(), is_proxy=False):
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
        return
    if sys.platform in ['linux', 'darwin'] and ss.method not in method_set_shadowsocks_x:
        return

    ip = socket.getaddrinfo(ss.server, None)[0][4][0]
    if ':' in ip:
        inet = socket.AF_INET6
    else:
        inet = socket.AF_INET
    sock = socket.socket(inet)
    sock.settimeout(0.8)  # 设置超时时间
    status = sock.connect_ex((ip, int(ss.server_port)))
    sock.close()
    if status == 0:
        aq.put(ss)


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


def crawl_ss(crawler, aq, is_local_proxy=False):
    cur_proc = multiprocessing.current_process()
    print("进程 {0} 启动，开始抓取配置...".format(cur_proc.name))
    data = crawler.crawl(is_local_proxy=is_local_proxy)
    print("进程 {0} 共抓取数据 {1} 条".format(cur_proc.name, len(data)))
    ss_check_count = 100  # 指定每一个进程最多有多少个协成
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


def set_ss_config_by_mac(sss):
    def ss2linux_ss(ss: Shadowsocks):
        return LinuxShadowsocks("", ss.remarks,
                                str(uuid.uuid1()).upper(),
                                ss.method, ss.server_port,
                                ss.password,
                                ss.server, "")

    linux_sss = [ss2linux_ss(ss) for ss in sss]
    ss_config_path = os.path.join(os.path.expanduser('~/Library/Preferences'), "com.qiuyuzhou.ShadowsocksX-NG.plist")
    ss_local_config_path = os.path.join(os.path.expanduser("~/Library/Application Support/ShadowsocksX-NG"),
                                        "ss-local-config.json")
    # 查找 ShadowsocksX-NG 程序是否已经启动
    shadowsocks_x_path = ""
    for proc in psutil.process_iter():
        if proc.name() == 'ShadowsocksX-NG':
            print("ShadowsocksX-NG已启动")
            # 已经启动就记录下程序的启动路径，然后关闭程序，等待更新完成配置文件后在启动
            shadowsocks_x_path = proc.exe()
            print("关闭ShadowsocksX-NG程序，等待配置文件更新后重新启动")
            proc.terminate()
            break

    try:
        # 更新配置文件
        with open(ss_config_path, "rb") as f:
            content = f.read()
        args = ["plutil", "-convert", "json", "-o", "-", "--", "-"]
        p = Popen(args, stdin=PIPE, stdout=PIPE)
        out, err = p.communicate(content)
        ss_config = json.loads(out)
        ss_config["ServerProfiles"] = linux_sss
        ss_config_json = json.dumps(ss_config, cls=LinuxShadowsocksEncoder).encode()

        args = ["plutil", "-convert", "xml1", "-o", "-", "--", "-"]
        p = Popen(args, stdin=PIPE, stdout=PIPE)
        out, err = p.communicate(ss_config_json)
        ss_plist = out.decode()
        with open(ss_config_path, "r+") as f:
            f.writelines(ss_plist)
        print("更新ShadowsocksX-NG配置成功...")
        if os.path.exists(ss_local_config_path):
            os.remove(ss_local_config_path)
            print("删除ShadowsocksX-NG当前配置成功...")
    except Exception as ex:
        print(ex)

    if shadowsocks_x_path:
        print("ShadowsocksX-NG重新启动")
        os.popen(shadowsocks_x_path)


def build_url(url_proxy_dic, types=[], speed=None, area=[], exclude_area=[]):
    crawler_urls = []
    if not url_proxy_dic:
        return crawler_urls
    for base_url, is_proxy in url_proxy_dic.items():
        url = CrawlerUrl(base_url, types=set(types), speed=speed,
                         area=set(area), exclude_area=set(exclude_area),
                         is_proxy=is_proxy)
        crawler_urls.append(url)
    return crawler_urls


def create_ss_pool_crawler_process(ua_manager, ssq, crawler_urls):
    crawlers = []
    if not crawler_urls:
        return crawlers
    for crawler_url in crawler_urls:
        crawler = SspoolCrawler(ua_manager, url=crawler_url.url)
        crawler_pro = Process(target=crawl_ss, args=(crawler, ssq, crawler_url.is_proxy))
        crawler_pro.name = urlparse(crawler.url).netloc  # 使用域名来做为的名字
        crawlers.append(crawler_pro)
    return crawlers


def main(types=None, speed=None, ss_count=None, area=None, exclude_area=None, ip_sort=1):
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

    if types is None:
        types = []
    if area is None:
        area = []
    if exclude_area is None:
        exclude_area = []

    exclude_area.append("CN")  # 把国内的节点排除掉
    print("启动抓取程序,要抓取节点的类型：{0}，速度：{1}，节点的个数：{2}".format(types, speed, ss_count))

    start_time = time.time()
    uaManager = UserAgentManager()
    available_data_queue = Queue()

    url_proxy_dic = {
        "https://free.kingfu.cf/clash/proxies": False,
        "https://proxy.51798.xyz/clash/proxies": False,
        "https://hello.stgod.com/clash/proxies": False,
        "https://proxypool.fly.dev/clash/proxies": False,
        "https://fq.lonxin.net/clash/proxies": False,
        "https://free.dswang.ga/clash/proxies": False,
        "https://sspool.herokuapp.com/clash/proxies": False,
        "https://www.qunima.cc/clash/proxies": False,
        "https://ss.dswang.ga:8443/clash/proxies": False,
        "http://8.135.91.61/clash/proxies": False,
        "https://www.linbaoz.com/clash/proxies": False
    }
    crawler_urls = build_url(url_proxy_dic, types=types, speed=speed, area=area, exclude_area=exclude_area)
    crawlers = create_ss_pool_crawler_process(uaManager, available_data_queue, crawler_urls)
    monkey.patch_all()  # 实现了协程任务的调度
    # 启动爬虫进程
    for crawler in crawlers:
        crawler.start()

    # Shadowsocks 过滤或可用的账号列表, 在主线程中进行收集
    ss_set = set()
    flag = True
    while flag:
        while not available_data_queue.empty():
            ss = available_data_queue.get(True)
            print("可用 {0}".format(str(ss)))
            ss_set.add(ss)
            if 0 < ss_count == len(ss_set):
                for crawler in crawlers:
                    if crawler.is_alive():
                        crawler.terminate()
        for crawler in crawlers:
            if crawler.is_alive():
                break
        else:
            flag = False

    print("共有", len(ss_set), "个服务可以使用，准备配置 Shadowsocks")
    ss_list = list(ss_set)
    if ip_sort == 1:  # 按照ip排序
        ss_list.sort(key=lambda ss: ss.server)
    if sys.platform in ['win32', 'cygwin']:
        set_ss_config(ss_list)
    elif sys.platform in ['linux', 'darwin']:
        set_ss_config_by_mac(ss_list)
    print("完成, 中耗时：{0} 秒".format(time.time() - start_time))


if __name__ == '__main__':
    # 使用IDE调试用这两句代码
    # main(types=["ss"], speed=300, ss_count=500, area=None, exclude_area=["CN"])
    # exit(0)
    # 正常运行注释上面两句代码
    parser = argparse.ArgumentParser(description='ArgUtils')
    parser.add_argument('-t', type=str, default="ss", help="节点的类型可同时选择多个类型,取值为：ss,ssr,vmess,trojan，默认为ss")
    parser.add_argument('-s', type=str, default=None, help="节点的速度任何数字，单个数字选择最低速度，两个数字选择速度区间，默认无限制")
    parser.add_argument('-a', type=str, default=None, help="节点的的所在地区可同时选择多个国家，取值为：AT,CN,IN,HK,JP,NL,RU,SG,TW,US...")
    parser.add_argument('-e', type=str, default="CN",
                        help="排除某些地区的节点可同时选择多个国家，取值为：AT,CN,IN,HK,JP,NL,RU,SG,TW,US...，默认排除中国的节点")
    parser.add_argument('-n', type=int, default=-1, help="要抓取节点的数量，默认无限制")
    parser.add_argument('-i', type=int, default=1, help="抓取的结果按ip排序，默认是")
    args = parser.parse_args()

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

    area = [] if args.a is None or args.a == "None" else args.a.split(",")

    main(types=types, speed=speed, ss_count=args.n, area=area, exclude_area=args.e.split(","), ip_sort=args.i)
