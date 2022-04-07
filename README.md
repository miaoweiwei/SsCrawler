# SsCrawler
自动抓取网络上的ss账户并自动配置shadowsocks服务器或者MAC OS 上的 ShadowsocksX-NG

| 系统类型 | 代理软件                                                     |
| -------- | ------------------------------------------------------------ |
| windows  | [Shadowsocks](https://github.com/shadowsocks/shadowsocks-windows/releases) |
| Mac OS   | [ShadowsocksX-NG](https://github.com/shadowsocks/ShadowsocksX-NG/releases) |

## 安装
你需要有python3的环境，
```shell
git clone https://github.com/miaoweiwei/SsCrawler.git
```
clone代码后，在指定的python3的环境中安装 packages.txt 中指定的依赖包
```shell
pip install -r packages.txt
```

## 执行
支持在终端里进行操作，根据命令的提示进行相应的操作即可

![image](https://user-images.githubusercontent.com/20410007/138589319-c771f88a-92da-49ba-9f3a-cf8736e7c865.png)

##  卸载ShadowsocksX-NG

```
rm -rf /Library/Application\ Support/ShadowsocksX-NG
rm -rf ~/Library/Application\ Support/ShadowsocksX-NG
rm -rf ~/Library/LaunchAgents/com.qiuyuzhou.shadowsocksX-NG.http.plist
rm -rf ~/Library/LaunchAgents/com.qiuyuzhou.shadowsocksX-NG.local.plist
rm -rf ~/.ShadowsocksX-NG
rm -rf ~/Library/Preferences/com.qiuyuzhou.ShadowsocksX-NG.plist
rm -rf ~/Library/Caches/com.qiuyuzhou.ShadowsocksX-NG
```
