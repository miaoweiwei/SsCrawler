import os
import sys

if sys.platform in ['linux', 'darwin']:
    if os.geteuid() != 0:
        # os.system("ulimit -n 10240\nsudo python app.py\n")
        ss_config_path = os.path.join(os.path.expanduser('~/Library/Preferences'),
                                      "com.qiuyuzhou.ShadowsocksX-NG.plist")
        if os.path.exists(ss_config_path):
            os.system("ulimit -n 10240\npython app.py\n")
        else:
            print("你的电脑上没有安装ShadowsocksX-NG，请先安装该软件")
            print("下载地址：https://github.com/shadowsocks/ShadowsocksX-NG/releases/download/v1.9.4/ShadowsocksX-NG.1.9.4.zip")
else:
    os.system("python app.py\n")
