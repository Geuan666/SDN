#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time
import os
import sys


def createDatacenterNet():
    # 创建网络并添加节点
    net = Mininet(controller=RemoteController, link=TCLink, switch=OVSKernelSwitch)

    # 添加控制器
    controller_ip = os.environ.get('CONTROLLER_IP', '127.0.0.1')
    info(f'*** 添加控制器 (IP: {controller_ip})\n')
    c0 = net.addController('c0', controller=RemoteController, ip=controller_ip, port=6633)

    # 添加交换机 - 外部网络
    info('*** 添加外部网络交换机\n')
    external_switch = net.addSwitch('ex', dpid='0000000000000001')

    # 添加交换机 - 数据中心网络
    info('*** 添加数据中心网络交换机\n')
    # 边缘路由器
    edge_router = net.addSwitch('ed', dpid='0000000000000002')

    # 汇聚层交换机
    spine1 = net.addSwitch('s1', dpid='0000000000000003')
    spine2 = net.addSwitch('s2', dpid='0000000000000004')
    spine3 = net.addSwitch('s3', dpid='0000000000000005')

    # 接入层交换机
    leaf1 = net.addSwitch('l1', dpid='0000000000000006')
    leaf2 = net.addSwitch('l2', dpid='0000000000000007')
    leaf3 = net.addSwitch('l3', dpid='0000000000000008')
    leaf4 = net.addSwitch('l4', dpid='0000000000000009')
    leaf5 = net.addSwitch('l5', dpid='000000000000000a')

    # 注意：统一所有主机到一个单一的平坦网络 10.0.0.0/8
    info('*** 添加外部网络主机\n')
    h6 = net.addHost('h6', mac='00:00:00:00:00:06', ip='10.0.0.6/8')
    h7 = net.addHost('h7', mac='00:00:00:00:00:07', ip='10.0.0.7/8')
    h8 = net.addHost('h8', mac='00:00:00:00:00:08', ip='10.0.0.8/8')

    # 添加主机 - 数据中心网络主机
    info('*** 添加数据中心网络主机\n')
    # Leaf1连接的主机
    h1a = net.addHost('h1a', mac='00:00:00:00:01:01', ip='10.0.0.11/8')
    h1b = net.addHost('h1b', mac='00:00:00:00:01:02', ip='10.0.0.12/8')

    # Leaf2连接的主机
    h2a = net.addHost('h2a', mac='00:00:00:00:02:01', ip='10.0.0.21/8')
    h2b = net.addHost('h2b', mac='00:00:00:00:02:02', ip='10.0.0.22/8')

    # Leaf3连接的主机
    h3a = net.addHost('h3a', mac='00:00:00:00:03:01', ip='10.0.0.31/8')
    h3b = net.addHost('h3b', mac='00:00:00:00:03:02', ip='10.0.0.32/8')

    # Leaf4连接的主机
    h4a = net.addHost('h4a', mac='00:00:00:00:04:01', ip='10.0.0.41/8')
    h4b = net.addHost('h4b', mac='00:00:00:00:04:02', ip='10.0.0.42/8')

    # Leaf5连接的清洗服务器
    h5a = net.addHost('h5a', mac='00:00:00:00:05:01', ip='10.0.0.51/8')
    h5b = net.addHost('h5b', mac='00:00:00:00:05:02', ip='10.0.0.52/8')
    h5c = net.addHost('h5c', mac='00:00:00:00:05:03', ip='10.0.0.53/8')

    # 创建链路 - 外部网络
    info('*** 创建外部网络链路\n')
    net.addLink(external_switch, h6)
    net.addLink(external_switch, h7)
    net.addLink(external_switch, h8)

    # 创建链路 - 外部网络连接到数据中心
    info('*** 创建外部网络到数据中心的链路\n')
    net.addLink(external_switch, edge_router)

    # 创建链路 - 数据中心内部
    info('*** 创建数据中心内部链路\n')
    # 边缘路由器连接汇聚层
    net.addLink(edge_router, spine1)
    net.addLink(edge_router, spine2)
    net.addLink(edge_router, spine3)

    # 汇聚层连接接入层
    net.addLink(spine1, leaf1)
    net.addLink(spine1, leaf2)
    net.addLink(spine1, leaf3)
    net.addLink(spine1, leaf4)
    net.addLink(spine1, leaf5)

    net.addLink(spine2, leaf1)
    net.addLink(spine2, leaf2)
    net.addLink(spine2, leaf3)
    net.addLink(spine2, leaf4)
    net.addLink(spine2, leaf5)

    net.addLink(spine3, leaf1)
    net.addLink(spine3, leaf2)
    net.addLink(spine3, leaf3)
    net.addLink(spine3, leaf4)
    net.addLink(spine3, leaf5)

    # 接入层连接主机
    net.addLink(leaf1, h1a)
    net.addLink(leaf1, h1b)

    net.addLink(leaf2, h2a)
    net.addLink(leaf2, h2b)

    net.addLink(leaf3, h3a)
    net.addLink(leaf3, h3b)

    net.addLink(leaf4, h4a)
    net.addLink(leaf4, h4b)

    net.addLink(leaf5, h5a)
    net.addLink(leaf5, h5b)
    net.addLink(leaf5, h5c)

    # 启动网络
    info('*** 启动网络\n')
    net.build()

    # 启动控制器
    info('*** 启动控制器\n')
    c0.start()

    # 启动所有交换机
    info('*** 启动交换机\n')
    external_switch.start([c0])
    edge_router.start([c0])
    spine1.start([c0])
    spine2.start([c0])
    spine3.start([c0])
    leaf1.start([c0])
    leaf2.start([c0])
    leaf3.start([c0])
    leaf4.start([c0])
    leaf5.start([c0])

    # 等待控制器连接
    info('*** 等待控制器连接\n')
    time.sleep(5)

    # 配置交换机STP启用
    info('*** 配置STP (避免环路)\n')
    for s in net.switches:
        s.cmd('ovs-vsctl set bridge {} stp_enable=true'.format(s.name))
    time.sleep(2)  # 等待STP收敛

    # 确保主机间通信
    info('*** 触发初始ARP请求\n')
    for h in net.hosts:
        for target in net.hosts:
            if h != target:
                h.cmd('ping -c 1 -W 1 {} >/dev/null 2>&1 &'.format(target.IP()))

    return net


if __name__ == '__main__':
    setLogLevel('info')
    net = createDatacenterNet()

    # 确保stdout/stderr被刷新
    sys.stdout.flush()
    sys.stderr.flush()

    info('*** 运行命令行界面\n')
    CLI(net)

    info('*** 停止网络\n')
    net.stop()