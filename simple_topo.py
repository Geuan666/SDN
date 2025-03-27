#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import os
import sys

def createNet():
    # 创建网络并添加节点
    net = Mininet(controller=RemoteController, link=TCLink, switch=OVSKernelSwitch)

    # 添加控制器
    # 获取控制器IP，如果环境变量设置了CONTROLLER_IP则使用环境变量的值，否则使用127.0.0.1
    controller_ip = os.environ.get('CONTROLLER_IP', '127.0.0.1')
    info(f'*** 添加控制器 (IP: {controller_ip})\n')
    c0 = net.addController('c0', controller=RemoteController, ip=controller_ip, port=6633)

    # 添加交换机
    info('*** 添加交换机\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')

    # 添加主机
    info('*** 添加主机\n')
    h1 = net.addHost('h1', mac='00:00:00:00:00:01', ip='10.0.0.1/24')
    h2 = net.addHost('h2', mac='00:00:00:00:00:02', ip='10.0.0.2/24')
    h3 = net.addHost('h3', mac='00:00:00:00:00:03', ip='10.0.0.3/24')
    h4 = net.addHost('h4', mac='00:00:00:00:00:04', ip='10.0.0.4/24')

    # 添加链路
    info('*** 创建链路\n')
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s2)
    net.addLink(h4, s3)
    net.addLink(s1, s2)
    net.addLink(s2, s3)

    # 启动网络
    info('*** 启动网络\n')
    net.build()
    info('*** 启动控制器\n')
    c0.start()
    
    info('*** 启动交换机\n')
    s1.start([c0])
    s2.start([c0])
    s3.start([c0])

    # 等待控制器连接
    info('*** 等待控制器连接\n')
    time.sleep(3)  # 增加等待时间确保控制器完全启动

    # 返回网络
    return net

if __name__ == '__main__':
    setLogLevel('info')
    net = createNet()
    
    # 确保stdout/stderr被刷新
    sys.stdout.flush()
    sys.stderr.flush()
    
    info('*** 运行命令行界面\n')
    # 使用阻塞模式启动CLI，确保显示并接受输入
    CLI(net)
    
    info('*** 停止网络\n')
    net.stop() 