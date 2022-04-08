#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2021/4/14 23:43
@Author  : miaozi
@File    : user_agent_crawler.py
@Software: PyCharm
@Desc    : 
"""
import json
import math
import random
import sys
import os
import re
import time
from typing import Any
from urllib import parse as urlparse
from urllib import request

from bs4 import BeautifulSoup


class UserAgent(object):
    def __init__(self, kwargs=None):
        self.equipment_type = "PC"
        self.system_type = "Windows"
        self.equipment_name = "Win10"
        self.browser_type = "Chrome"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"

        if kwargs:
            self.__dict__ = kwargs

    def __str__(self) -> str:
        """str形式"""
        return '{"equipment_type":"%s", "system_type":"%s", "equipment_name":"%s", "browser_type":"%s", "user_agent":"%s"}' % (
            self.equipment_type, self.system_type, self.equipment_name, self.browser_type, self.user_agent)

    def __repr__(self) -> str:
        """在命令行状态下返回其str形式"""
        return str(self)

    def __attrs(self):
        return self.equipment_type, self.system_type, self.equipment_name, self.browser_type, self.user_agent

    def __hash__(self) -> int:
        """为了确保每一个对象如果属性不同就有不同的hash值"""
        return hash(self.__attrs())

    def __eq__(self, o: object) -> bool:
        """equals方法"""
        return o and isinstance(o, UserAgent) and \
               self.equipment_type == o.equipment_type and \
               self.system_type == o.system_type and \
               self.equipment_name == o.equipment_name and \
               self.browser_type == o.browser_type and \
               self.user_agent == o.user_agent


class UserAgentEncoder(json.JSONEncoder):

    def default(self, o: Any) -> Any:
        if isinstance(o, UserAgent):
            return o.__dict__
        return json.JSONEncoder.default(self, o)


class HtmlDownloader(object):
    def download(self, url, user_agent=None, headers=None):
        if url is None:
            return None
        if headers is None:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) coc_coc_browser/94.0.202 Chrome/88.0.4324.202 Safari/537.36"
            }
        if user_agent:
            headers["User-Agent"] = user_agent
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
        req = request.Request(url=url, headers=headers)
        response = request.urlopen(req, timeout=10)
        if response.getcode() != 200:  # 不等于200说明请求失败
            return None
        return response.read()


class HtmlParser(object):
    def parse(self, html_cont):
        if html_cont is None:
            return
        soup = BeautifulSoup(html_cont, "lxml", from_encoding="utf-8")
        new_urls = self.__get_new_urls__(soup)
        new_data = self.__get_new_data__(soup)
        return new_urls, new_data

    def __get_new_urls__(self, soup):
        new_urls = set()
        hvtmenutype = soup.find_all('div', class_="hvtmenutype")
        links = [link for item in hvtmenutype for link in item.find_all('a')]
        for link in links:
            new_url = link["href"]
            new_urls.add(new_url)
        return new_urls

    def __get_new_data__(self, soup):
        ua_list = []
        table = soup.find("table", class_="table table-bordered")
        uas = table.find_all('tr')
        for item in uas[1:]:  # 从1开始，因为要去掉标题
            ua = UserAgent()
            row = item.find_all('td')
            ua.equipment_type = row[0].text.strip()
            ua.system_type = row[1].text.strip()
            ua.equipment_name = row[2].text.strip()
            ua.browser_type = row[3].text.strip()
            user_agent = row[4].text.strip()
            if "..." in user_agent:
                user_agent = re.sub("(\.\.\.)+", "", row[4].text.strip(), count=0, flags=0)
            ua.user_agent = user_agent
            ua_list.append(ua)
        return ua_list


class UrlManager(object):
    def __init__(self, retry_num=3):
        self.new_urls = set()
        self.old_urls = set()
        self.failure_url_dic = dict()
        self.retry_num = retry_num
        self.retry_urls = []

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

    def add_failure_url(self, failure_url):
        if failure_url:
            if failure_url in self.failure_url_dic:
                self.failure_url_dic[failure_url] += 1
                if self.failure_url_dic[failure_url] >= self.retry_num:
                    self.retry_urls.remove(failure_url)
            else:
                self.failure_url_dic[failure_url] = 0
                self.retry_urls.append(failure_url)

    def get_failure_url(self):
        return self.retry_urls[-1]

    def remove_failure_url(self, retry_url):
        if retry_url:
            if retry_url in self.failure_url_dic:
                self.failure_url_dic.pop(retry_url)
                self.retry_urls.remove(retry_url)

    def has_failure_url(self):
        return True if self.failure_url_dic else False

    def has_failure_retry_url(self):
        return True if self.retry_urls else False

    def save_failure_url(self, file_path=None):
        if file_path is None:
            file_path = "../config/failure_url_user_agent.txt"
        with open(file_path, "w") as f:
            json.dump(self.retry_urls, f)

        print("\n保存完成")


class HtmlOutput(object):
    def __init__(self):
        self.data = set()

    def collect_data(self, new_data):
        if new_data:
            self.data |= set(new_data)

    def get_data(self):
        if self.data:
            return list(self.data)
        return None

    def get_ua_random(self):
        """随机返回一个数据"""
        if self.data:
            return random.choice(list(self.data))
        return None

    def get_pc_ua_random(self):
        """随机返回PC上的一个user_agent"""
        if self.data:
            pc_ua = [item for item in self.data if item.equipment_type.lower() == 'pc']
            return random.choice(pc_ua)
        return None

    def save2file(self, file_path):
        if file_path is None:
            file_path = "../config/user_agent.txt"
        with open(file_path, 'w') as f:
            json.dump(list(self.data), f, cls=UserAgentEncoder)
        print("\n保存完成")


class MainCrawler(object):
    def __init__(self, hd, hp, ho, um, url_root=None):
        self.htmlDownload = hd
        self.htmlParse = hp
        self.htmlOutput = ho
        self.urlManager = um
        self.url_root = url_root
        self.urlManager.add_new_url(url_root)

    def crawl(self, save_fre=20, save_path=None, failure_url_path=None):
        ua = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) coc_coc_browser/94.0.202 Chrome/88.0.4324.202 Safari/537.36"
        i = 1
        start_time = time.time()
        while self.urlManager.has_new_url():
            url_temp = self.urlManager.get_new_url()
            new_full_url = urlparse.urljoin(self.url_root, url_temp)  # 将两个url拼接成一个新的url
            try:
                user_agent = self.htmlOutput.get_ua_random()
                if user_agent:
                    ua = user_agent.user_agent
                html_cont = self.htmlDownload.download(new_full_url, user_agent=ua)
                urls, datas = self.htmlParse.parse(html_cont)

                if html_cont is None or datas is None:
                    self.urlManager.add_failure_url(url_temp)
                else:
                    self.urlManager.add_new_urls(urls)
                    self.htmlOutput.collect_data(datas)
                    self.urlManager.add_old_url(url_temp)
            except Exception as ex:
                self.urlManager.add_failure_url(url_temp)
                print("\n{0} crawl failed {1}".format(new_full_url, ex))

            run_time = time.time() - start_time
            hour = int(run_time // 3600)
            minute = int((run_time % 3600) // 60)
            seconds = math.ceil((run_time % 3600) % 60)
            sys.stdout.flush()
            print("\r运行时间 {0}:{1}:{2} 已经抓取了 {3} 个网页 当前抓取 {4}".format(hour, minute, seconds, i, new_full_url), end='')

            if i % save_fre == 0:
                self.htmlOutput.save2file(save_path)
            i += 1
            time.sleep(0.1)
        self.htmlOutput.save2file(save_path)
        self.urlManager.save_failure_url(failure_url_path)

    def failed_retry(self, retry_num=3, time_interval=1, save_fre=20, save_path=None):
        if self.urlManager.has_failure_url() is False:
            return
        self.urlManager.retry_num = retry_num
        ua = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) coc_coc_browser/94.0.202 Chrome/88.0.4324.202 Safari/537.36"
        i = 1
        start_time = time.time()
        while self.urlManager.has_failure_retry_url():
            url_temp = self.urlManager.get_failure_url()
            new_full_url = urlparse.urljoin(self.url_root, url_temp)  # 将两个url拼接成一个新的url
            try:
                user_agent = self.htmlOutput.get_ua_random()
                if user_agent:
                    ua = user_agent.user_agent
                html_cont = self.htmlDownload.download(new_full_url, user_agent=ua)
                urls, datas = self.htmlParse.parse(html_cont)
                if html_cont is None or datas is None:
                    self.urlManager.add_failure_url(url_temp)
                else:
                    self.urlManager.add_new_urls(urls)
                    self.htmlOutput.collect_data(datas)
                    self.urlManager.add_old_url(url_temp)
                    self.urlManager.remove_failure_url(url_temp)
            except Exception as ex:
                self.urlManager.add_failure_url(url_temp)
                print("\n{0} crawl failed {1}".format(new_full_url, ex))

            run_time = time.time() - start_time
            hour = int(run_time // 3600)
            minute = int((run_time % 3600) // 60)
            seconds = math.ceil((run_time % 3600) % 60)
            sys.stdout.flush()
            print("\r运行时间 {0}:{1}:{2} 已经抓取了 {3} 个网页 当前抓取 {4}".format(hour, minute, seconds, i, new_full_url), end='')

            if i % save_fre == 0:
                self.htmlOutput.save2file(save_path)
            i += 1

    def save(self, file_path):
        self.htmlOutput.save2file(file_path)

    def get_data(self):
        self.htmlOutput.get_data()


class UserAgentManager(object):
    def __init__(self, ua_path=None):
        if not ua_path:
            root_path = os.path.abspath(os.path.dirname(__file__)).split('SsCrawler')[0]
            ua_path = os.path.join(root_path, "SsCrawler/config/user_agent.txt")
        with open(ua_path, 'r') as f:
            self.data = json.load(f, object_hook=UserAgent)

    def get_user_agent(self, equipment_type=None, system_type=None, equipment_name=None, browser_type=None):
        temp = [ua for ua in self.data if (equipment_type is None or ua.equipment_type == equipment_type) and (
                system_type is None or ua.system_type == system_type) and (
                        equipment_name is None or ua.equipment_name == equipment_name) and (
                        browser_type is None or ua.browser_type == browser_type)]
        return temp

    def get_user_agent_random(self, equipment_type=None, system_type=None, equipment_name=None, browser_type=None):
        temp = self.get_user_agent(equipment_type=equipment_type, system_type=system_type,
                                   equipment_name=equipment_name, browser_type=browser_type)
        return random.choice(temp)

    def get_equipment_types(self):
        return [ua.equipment_type for ua in self.data if ua.equipment_type]

    def get_system_types(self):
        return [ua.system_type for ua in self.data if ua.system_type]

    def get_equipment_names(self):
        return [ua.equipment_name for ua in self.data if ua.equipment_name]

    def get_browser_types(self):
        return [ua.browser_type for ua in self.data if ua.browser_type]


if __name__ == '__main__':
    url = "http://useragent.kuzhazha.com/"
    download = HtmlDownloader()
    parser = HtmlParser()
    output = HtmlOutput()
    url_manager = UrlManager()
    main = MainCrawler(download, parser, output, url_manager, url_root=url)
    main.crawl(save_fre=100)
    print("爬取完成")

    # ua_dic = {
    #     "equipment_type": '手机', "system_type": "Android", "equipment_name": "LG手机", "browser_type": "Chrome",
    #     "user_agent": '1234665464'
    # }
    # ua = UserAgent(ua_dic)
    # # 对象转 json 字符串
    # ua_str = json.dumps(ua, cls=UserAgentEncoder)
    # print(ua_str)
    # ua1 = json.loads(ua_str, object_hook=UserAgent)
    # print(isinstance(ua1, UserAgent))
    # # 这里你会发现没有date_of_brith这个内容
    # print(ua1.__dict__)

    # root_path = os.path.abspath(os.path.dirname(__file__)).split('SsCrawler')[0]
    # ua_path = os.path.join(root_path, "SsCrawler/config/user_agent.txt")
    uas = UserAgentManager()
    print(uas.get_user_agent_random())
