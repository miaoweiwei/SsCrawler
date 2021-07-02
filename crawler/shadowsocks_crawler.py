#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2021/4/19 14:50
@Author  : miaozi
@File    : shadowsocks_crawler.py
@Software: PyCharm
@Desc    : 
"""
import json
import math
import socket
import sys
import threading
import time
from typing import Any
from urllib import parse as urlparse
from urllib import request

import yaml
from bs4 import BeautifulSoup

from crawler import UserAgentManager


# from user_agent_crawler import UserAgentManager


# sys.setrecursionlimit( 2000 )
# socket.setdefaulttimeout(30)


def check_ip_port(host, port):
    """函数返回True，表示端口是能连接的；函数返回False，表示端口是不能连接的。"""
    ip = socket.getaddrinfo(host, None)[0][4][0]
    if ':' in ip:
        inet = socket.AF_INET6
    else:
        inet = socket.AF_INET
    sock = socket.socket(inet)
    status = sock.connect_ex((ip, int(port)))
    sock.close()
    return status == 0


status_data = []
lock = threading.Lock()
threads = []


def check_contain_chinese(check_str):
    """检测字符串是不是中文"""
    if check_str:
        for ch in check_str:
            if u'\u4e00' <= ch <= u'\u9fff':  # 基本汉字 和 基本汉字补充
                return True
    return False


class Shadowsocks(object):
    def __init__(self, kwargs=None):
        self.server = "127.0.0.1"
        self.server_port = 1088
        self.password = "123456"
        self.method = "aes-256-gcm"
        self.timeout = 5
        self.remarks = ''
        if kwargs and isinstance(kwargs, dict):
            self.__dict__ = kwargs

    def __str__(self) -> str:
        return '{"server":"%s", "server_port":%d, "password":"%s", "method":"%s", "timeout":%d, "remarks":"%s"}' % (
            self.server, self.server_port, self.password, self.method, self.timeout, self.remarks)

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, o: object) -> bool:
        """对比两个 Shadowsocks 对象是否一样"""
        # return o and isinstance(o, Shadowsocks) and \
        #        self.server == o.server and \
        #        self.server_port == o.server_port and \
        #        self.password == o.password and \
        #        self.method == o.method and \
        #        self.timeout == o.timeout and \
        #        self.remarks == o.remarks
        # TODO 我们这里判断 ip 和端口是不是一样的就可以判断服务器是不是一样的
        return o and isinstance(o, Shadowsocks) and \
               self.server == o.server and \
               self.server_port == o.server_port

    def __attrs(self):
        """为了确保每一个对象如果属性不同就有不同的hash值"""
        return self.server, self.server_port, self.password, self.method, self.timeout, self.remarks

    def __hash__(self) -> int:
        """为了确保每一个对象如果属性不同就有不同的hash值"""
        return hash(self.__attrs())


class ShadowsocksEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Shadowsocks):
            return o.__dict__
        return json.JSONEncoder.default(self, o)


class ShadowsocksManager(object):
    def __init__(self, ua_path="shadowsocks.txt"):
        if ua_path:
            with open(ua_path, 'r') as f:
                self.data = json.load(f, object_hook=Shadowsocks)

    def get_ss(self):
        pass


class HtmlDownloader(object):
    def __init__(self, url_root=None):
        self.url_root = url_root

    def download(self, url, user_agent=None, headers=None, is_local_proxy=True):
        if url is None:
            return None
        if headers is None:
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) coc_coc_browser/94.0.202 Chrome/88.0.4324.202 Safari/537.36",
            }
        if user_agent:
            headers["user-agent"] = user_agent
        # 组织 Request 数据
        req = request.Request(url=url, headers=headers)
        question_index = url.find("?")
        if question_index > 0:  # ? 后面的参数都需要编码
            param_str = url[question_index + 1:]
            params = param_str.split('&')
            param_str = ""
            for i, param in enumerate(params):
                eq_index = param.find("=")
                if eq_index > 0:
                    param_str += urlparse.quote(param[:eq_index]) + "=" + urlparse.quote(param[eq_index + 1:])
                else:
                    param_str += urlparse.quote(param)
                if i < len(params) - 1:
                    param_str += '&'
            url = url[:question_index] + "?" + param_str
        if self.url_root not in url:
            url = urlparse.urljoin(self.url_root, url)
        # 请求
        # 代理设置
        if is_local_proxy:
            # 1创建 ProxyHeader
            proxy_header = request.ProxyHandler(
                {
                    'http': "127.0.0.1:1088",  # ip地址 ip:port
                    'https': "127.0.0.1:1088"  # ip地址 ip:port
                }
            )
            # 2新建opener对象
            proxy_opener = request.build_opener(proxy_header)
            response = proxy_opener.open(req)
        else:
            response = request.urlopen(req, timeout=10)
        if response.getcode() != 200:  # 不等于200说明请求失败
            return None
        return response.read()


class HtmlParser(object):
    def __init__(self, encoding='utf-8', html_downloader=None, ua_manager=None):
        self.encoding = encoding
        self.download = html_downloader
        self.uaManager = ua_manager

    def parse_ss_links(self, html_cont):
        if html_cont is None:
            return
        soup = BeautifulSoup(html_cont, "lxml", from_encoding=self.encoding)
        new_urls = self.__get_new_url(soup)
        return new_urls

    def __get_new_url(self, soup):
        new_urls = set()
        ss_accounts = soup.find_all('ul')
        for ss_account in ss_accounts[1:]:
            links = ss_account.find_all("a")
            for link in links:
                temp_url = link['href']
                # 直接使用这里的 url 服务器会返回对应的与PC端的Html数据
                # 但是好像，pc端的html内部要先 执行 一些 js 代码
                # 所以这里使用 对应的手机端的 url 好处是不用考虑执行js的问题
                # 就是在 temp_url 这个url前面加一个 '/m'
                # 然后 User Agent 设置成手机端的
                temp_url = "/m" + temp_url  # 对应的手机端的 url
                if self.download:
                    try:
                        temp_ua = self.uaManager.get_user_agent_random(equipment_type="手机")  # 设置 User_Agent为手机端的
                        temp_html = self.download.download(temp_url, user_agent=temp_ua.user_agent)
                        temp_url = self.__get_url_for_temp_url__(temp_html)
                        new_urls.add(temp_url)
                    except Exception as ex:
                        print("\n{0} crawl failed {1}".format(temp_url, ex))
        return new_urls

    def __get_url_for_temp_url__(self, html_cont):
        """提取shadowsocks账户对应的"""
        if html_cont is None:
            return
        soup = BeautifulSoup(html_cont, "lxml", from_encoding=self.encoding)
        fieldset = soup.find("fieldset")
        link = fieldset.find("a")
        return link["href"]

    def parse_ss(self, html_cont):
        """解析 Shadowsocks 配置信息"""
        new_data = set()
        if html_cont is None:
            return
        soup = BeautifulSoup(html_cont, "lxml", from_encoding=self.encoding)
        ps = soup.find_all('p')

        ss_str = ""
        for i, p_str in enumerate(ps):
            if 'yn:' == p_str.text.lower():  # 找到 ss 账户的位置
                if i + 2 < len(ps) and ps[i + 2].text:  # 账号 端口 密码 加密方式 等字段和表头的分开的
                    ss_str = ps[i + 2].text
                elif i + 1 < len(ps) and ps[i + 1].text:  # 账号 端口 密码 加密方式 等字段可能和表的头连在一起
                    ss_str = ps[i + 1].text
                break
        # 组织 Shadowsocks  对象
        ss_str_arr = ss_str.split('\n')
        for ss_str in ss_str_arr:
            ss_str = ss_str.strip()
            if check_contain_chinese(ss_str):  # 如果有中文就跳过
                continue
            sss = ss_str.split(" ")
            if sss and len(sss) != 4:  # 如果没有四个元素也跳过
                continue
            ss = Shadowsocks()
            ss.server = sss[0]
            ss.server_port = sss[1]
            ss.password = sss[2]
            ss.method = sss[3]
            new_data.add(ss)
        return new_data


class UrlManager(object):
    def __init__(self):
        self.new_urls = set()
        self.old_urls = set()

    def add_new_url(self, new_url):
        if new_url:
            if new_url not in self.new_urls and new_url not in self.old_urls:
                self.new_urls.add(new_url)

    def add_new_urls(self, urls):
        if urls:
            for new_url in urls:
                self.add_new_url(new_url)

    def has_new_url(self):
        return True if self.new_urls else False

    def get_new_url(self):
        return self.new_urls.pop()

    def add_old_url(self, old_url):
        if old_url:
            self.old_urls.add(old_url)


class HtmlOutput(object):
    def __init__(self):
        self.data = set()

    def collect_data(self, new_data):
        if new_data:
            if isinstance(new_data, set):
                self.data.update(new_data)
            elif isinstance(new_data, list):
                self.data.update(set(new_data))
            else:
                raise Exception("请填加 {0} 格式的数据处理方法".format(type(new_data)))

    def save2file(self, file_path=None):
        if file_path is None:
            file_path = "../config/shadowsocks.txt"
        with open(file_path, 'w') as f:
            json.dump(list(self.data), f, cls=ShadowsocksEncoder)
        print("\n保存完成")

    def delete_unavailable(self):
        """删除不可用的 shadowsocks 账号 信息"""
        pass


class MainCrawler(object):
    def __init__(self, hd, hp, ho, um, uam, url=None):
        self.htmlDownload = hd
        self.htmlParse = hp
        self.htmlOutput = ho
        self.urlManager = um
        self.uaManager = uam
        self.urlManager.add_new_url(url)

    def crawl(self, save_fre=20, save_path=None, failure_url_path=None):
        i = 1
        start_time = time.time()
        ua = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) coc_coc_browser/94.0.202 Chrome/88.0.4324.202 Safari/537.36"

        # 先爬取 Shadowsocks 账号的主页面里的 url
        url_temp = self.urlManager.get_new_url()
        user_agent = self.uaManager.get_user_agent_random()
        if user_agent:
            ua = user_agent.user_agent
        html_cont = self.htmlDownload.download(url_temp, user_agent=ua)
        urls = self.htmlParse.parse_ss_links(html_cont)
        self.urlManager.add_new_urls(urls)
        self.urlManager.add_old_url(url_temp)
        while self.urlManager.has_new_url():
            url_temp = self.urlManager.get_new_url()
            user_agent = self.uaManager.get_user_agent_random()
            if user_agent:
                ua = user_agent.user_agent
            try:
                html_cont = self.htmlDownload.download(url_temp, user_agent=ua)
                datas = self.htmlParse.parse_ss(html_cont)

                self.htmlOutput.collect_data(datas)
                self.urlManager.add_old_url(url_temp)
            except Exception as ex:
                print("\n{0} crawl failed {1}".format(url_temp, ex))
            run_time = time.time() - start_time
            hour = int(run_time // 3600)
            minute = int((run_time % 3600) // 60)
            seconds = math.ceil((run_time % 3600) % 60)
            sys.stdout.flush()
            print("\r运行时间 {0}:{1}:{2} 已经抓取了 {3} 个网页 当前抓取 {4}".format(hour, minute, seconds, i, url_temp), end='')
            i += 1

        self.htmlOutput.save2file(save_path)


if __name__ == '__main__':
    url = "https://www.freefq.com/free-ss/"
    url_root = "https://www.freefq.com"
    path = "/free-ss"
    uaManager = UserAgentManager()
    download = HtmlDownloader(url_root=url_root)
    html_parser = HtmlParser(html_downloader=download, ua_manager=uaManager)
    htmlOutput = HtmlOutput()
    urlManager = UrlManager()

    crawler = MainCrawler(download, html_parser, htmlOutput, urlManager, uaManager, url=path)
    crawler.crawl()

    # path = "https://www.freefq.com/d/file/free-ss/20210306/b1284a6fbeb9e7ed951df31cdf26494d.htm"
    ua = uaManager.get_user_agent_random(equipment_type="PC")
    # headers = {
    #     "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    #     "user-agent": ua.user_agent,
    #     "accept-encoding": "gzip, deflate, br"
    # }

    url_root = "https://sspool.herokuapp.com"
    path = "/clash/proxies"
    download = HtmlDownloader(url_root=url_root)
    html = download.download(path, user_agent=ua.user_agent, is_local_proxy=False)
    text = html.decode()
    text = yaml.load(text)
    # 过滤 选择其中的 Shadowsocks 账户
    sss = [ss for ss in text['proxies'] if ss['type'] == 'ss']
    print(sss)
