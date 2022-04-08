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
            "Host": multiprocessing.current_process().name,
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

    def __init__(self, uaManager, url=None):
        if url:
            self.url = url
        else:
            self.url = "https://sspool.herokuapp.com/clash/proxies"
        self.uaManager = uaManager

    def __format__(self, sspool_ss):
        """对从ss代理池中获取的ss账户进行转换成本地的格式"""
        s = Shadowsocks()
        s.server = sspool_ss['server']
        s.server_port = sspool_ss['port']
        s.password = sspool_ss['password']
        s.method = sspool_ss['cipher']
        s.remarks = sspool_ss['name']
        return s

    def crawl(self, proxy_type=None, country=None, none_country='CN', speed=None, is_local_proxy=False):
        """ 访问 https://sspool.herokuapp.com/ 这个代理池上的 Shadowsocks 免费账号

        :param proxy_type:      代理类型。取值 ss,ssr,vmess,trojan。可同时选择多个类型
        :param country:         服务器所在国家。取值 AT,CN,IN,HK,JP,NL,RU,SG,TW,US...	可同时选择多个国家
        :param none_country:    排除国家。取值 AT,CN,IN,HK,JP,NL,RU,SG,TW,US...	可同时选择多个国家
        :param speed:           访问速度，单个数字选择最低速度，两个数字选择速度区间(例如：10,30)
        :param is_local_proxy:  是否需要使用本地代理翻墙
        :return: Shadowsocks 免费账号列表
        """
        params = dict()
        if proxy_type:
            params['type'] = proxy_type
        if country:
            params['c'] = country
        if none_country:
            params['nc'] = none_country
        if speed:
            params['speed'] = speed
        ua = self.uaManager.get_user_agent_random()
        try:
            html_encode = download(self.url, params=params, user_agent=ua.user_agent, is_local_proxy=is_local_proxy)
            if html_encode:
                html_text = html_encode.decode()
                sss_json = yaml.load(html_text, Loader=yaml.SafeLoader)
                # 过滤 选择其中的 Shadowsocks 账户
                return [self.__format__(ss) for ss in sss_json['proxies'] if ss['type'] == 'ss']
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

    sspool_crawler = SspoolCrawler(uaManager)
    # data = sspool_crawler.crawl(proxy_type='ss', speed='100')
    # data = sspool_crawler.crawl()
    # print(data)

    clash_crawler = ClashCrawler(uaManager)
    sss = clash_crawler.crawl()
    print(sss)
