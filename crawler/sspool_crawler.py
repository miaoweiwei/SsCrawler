#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2021/5/1 18:19
@Author  : miaozi
@File    : sspool_crawler.py
@Software: PyCharm
@Desc    : 
"""
import multiprocessing
from urllib import parse as urlparse
from urllib import request

import yaml

from crawler import UserAgentManager, Shadowsocks

HTTP_PROXY = "127.0.0.1:1088",  # ip地址 ip:port
HTTPS_PROXY = "127.0.0.1:1088"  # ip地址 ip:port


def default_ctor(loader, tag_suffix, node):
    return node.value


def download(url, params=None, method='get', user_agent=None, headers=None, is_local_proxy=True):
    """ 下载指定url的页面内容
    @param url: url
    @param params: 如果url里带有了参数，那么这个params就不起作用
    @param method: 请求的方法
    @param user_agent: user_agent
    @param headers: header 请求头
    @param is_local_proxy: 是否使用本地代理
    @return: 返回页面的下载内容
    """
    if url is None:
        return None
    if headers is None:
        headers = {
            "Connection": "keep-alive",
            # "Host": multiprocessing.current_process().name,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) coc_coc_browser/94.0.202 Chrome/88.0.4324.202 Safari/537.36",
        }
    if user_agent:
        headers["user-agent"] = user_agent
    if method == 'get':
        question_index = url.find("?")
        if question_index > 0:  # ? 后面的参数都需要编码
            param_str = url[question_index + 1:]
            temp_params = param_str.split('&')
            param_str = ""
            for i, param in enumerate(temp_params):
                eq_index = param.find("=")
                if eq_index > 0:
                    param_str += urlparse.quote(param[:eq_index]) + "=" + urlparse.quote(param[eq_index + 1:])
                else:
                    param_str += urlparse.quote(param)
                if i < len(temp_params) - 1:
                    param_str += '&'
            url = url[:question_index] + "?" + param_str
        elif params:
            param_str = ""
            for j, item in enumerate(params.items()):
                param_str += urlparse.quote(item[0]) + '=' + urlparse.quote(item[1])
                if j < len(params) - 1:
                    param_str += "&"
            if param_str != '':
                url = urlparse.urljoin(url, '?' + param_str)
    elif method == 'post' and params:
        params = bytes(urlparse.urlencode(params), encoding='utf8')

    # 组织 request 数据
    if method == 'get':
        req = request.Request(url=url, headers=headers)
    elif params:  # 不是 get 请求就使用 post 先判断有没有参数
        req = request.Request(url=url, data=params, headers=headers)
    else:
        req = request.Request(url=url, headers=headers)

    try:

        # 发起请求
        # 判断是否需要代理设置
        if is_local_proxy:
            # 1创建 ProxyHeader
            proxy_header = request.ProxyHandler(
                {
                    'http': HTTP_PROXY,  # ip地址 ip:port
                    'https': HTTPS_PROXY  # ip地址 ip:port
                }
            )
            # 2新建opener对象
            proxy_opener = request.build_opener(proxy_header)
            response = proxy_opener.open(req, timeout=100)
        else:
            response = request.urlopen(req, timeout=100)
        # 不等于200说明请求失败
        return response.read() if response.getcode() == 200 else None
    except Exception as ex:
        print("{0}：{1}".format(urlparse.urlparse(url).netloc, ex))
        return None


class SspoolCrawler(object):
    """爬取https://sspool.herokuapp.com/上的 Shadowsocks 免费账号
        https://sspool.herokuapp.com/clash/proxies?c=CN,HK,TW&speed=15,30&type=ss

        接口参数说明：
            类型          type        ss,ssr,vmess,trojan	            可同时选择多个类型
            国家          c           AT,CN,IN,HK,JP,NL,RU,SG,TW,US...	可同时选择多个国家
            排除国家       nc          AT,CN,IN,HK,JP,NL,RU,SG,TW,US...	可同时选择多个国家
            速度          speed       任何数字                            单个数字选择最低速度
                                                                        两个数字选择速度区间
    """

    def __init__(self, uaManager, url=None, types={}, country={}, exclude_country={}, is_proxy=False):
        """ 创建一个 Sspool 爬虫
        @param uaManager: useragent 管理器
        @param url: 要爬取的url
        @param types: 抓取的代理类型
        @param country: 抓取ss所在地区
        @param exclude_country: 排除的地区
        @param is_proxy: 爬取时是否使用本地代理
        """
        self.uaManager = uaManager
        self.url = url
        self.types = types
        self.country = country
        self.exclude_country = exclude_country
        self.is_proxy = is_proxy

    def __format__(self, sspool_ss):
        """对从ss代理池中获取的ss账户进行转换成本地的格式"""
        s = Shadowsocks()
        s.server = sspool_ss['server']
        s.server_port = sspool_ss['port']
        s.password = sspool_ss['password']
        s.method = sspool_ss['cipher']
        s.remarks = sspool_ss['name']
        return s

    def filter(self, ss):
        if self.types:
            if 'type' not in ss or ss['type'] not in self.types:
                return False
        if self.country:
            if 'country' in ss and ss['country'] not in self.country:
                return False
        if self.exclude_country:
            if 'country' in ss and ss['country'] in self.exclude_country:
                return False
        return True

    def crawl(self):
        ua = self.uaManager.get_user_agent_random()
        try:
            html_encode = download(self.url, user_agent=ua.user_agent, is_local_proxy=self.is_proxy)
            if html_encode:
                html_text = html_encode.decode()
                # 解决 !<str> 也就是yaml 标签的问题
                yaml.add_multi_constructor('', default_ctor)
                sss_json = yaml.load(html_text, Loader=yaml.UnsafeLoader)
                # print(sss_json)
                # 过滤 选择其中的 Shadowsocks 账户
                if 'proxies' in sss_json and sss_json['proxies']:
                    return [self.__format__(ss) for ss in sss_json['proxies'] if self.filter(ss)]
        except Exception as ex:
            print("进程：{0} 发生异常：{1}".format(multiprocessing.current_process().name, ex))
        return []


class ClashCrawler(object):
    def __init__(self, uaManager):
        self.url = "https://raw.githubusercontent.com/ssrsub/ssr/master/Clash.yml"
        self.uaManager = uaManager

    def __format__(self, clash_ss):
        """对从ss代理池中获取的ss账户进行转换成本地的格式"""
        s = Shadowsocks()
        s.server = clash_ss['server']
        s.server_port = clash_ss['port']
        s.password = clash_ss['password']
        s.method = clash_ss['cipher']
        s.remarks = clash_ss['name']
        return s

    def crawl(self):
        ua = self.uaManager.get_user_agent_random()
        html_encode = download(self.url, user_agent=ua.user_agent, is_local_proxy=False)
        html_text = html_encode.decode()
        clash_json = yaml.load(html_text, Loader=yaml.SafeLoader)
        sss = {self.__format__(ss) for ss in clash_json['proxies'] if ss['type'] == 'ss'}
        return sss


if __name__ == '__main__':
    uaManager = UserAgentManager()
    url = "https://raw.githubusercontent.com/AzadNetCH/Clash/main/AzadNet.yml?type=ss,ssr&speed=10&nc=CN"
    url = "https://free886.herokuapp.com/clash/proxies?type=ssr,ss&speed=10&nc=CN"
    sspool_crawler = SspoolCrawler(uaManager, url, types='ss,ssr')
    data = sspool_crawler.crawl()
    print(data)

    # clash_crawler = ClashCrawler(uaManager)
    # sss = clash_crawler.crawl()
    # print(sss)

#     data_str = """port: 7890
# socks-port: 7891
# allow-lan: true
# proxies:
#   - {name: AE 🇦🇪 Sharjah @AzadNet, server: 109.169.72.249, port: 808, type: ss, cipher: chacha20-ietf-poly1305, password: G!yBwPWH3Vao, udp: true}
#   - {name: AZ 🇦🇿 @AzadNet, server: 94.20.154.38, port: 50000, type: ss, cipher: aes-256-cfb, password: !<str> 3135771619, udp: true}
#   - {name: FR 🇫🇷 @AzadNet, server: 5.39.70.138, port: 2376, type: ss, cipher: aes-256-gcm, password: faBAoD54k87UJG7, udp: true}"""
#     yaml.add_multi_constructor('', default_ctor)
#     test_data = yaml.load(data_str)
#     print(test_data)
