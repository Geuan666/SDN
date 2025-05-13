#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.node import Node
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
    # 确保dpid为1，与控制器一致
    external_switch = net.addSwitch('ex', dpid='0000000000000001', protocols='OpenFlow13')

    # 添加交换机 - 数据中心网络
    info('*** 添加数据中心网络交换机\n')
    # 边缘路由器 - 确保dpid为2，与控制器中的edge_router_dpid=2一致
    edge_router = net.addSwitch('ed', dpid='0000000000000002', protocols='OpenFlow13')

    # 汇聚层交换机
    spine1 = net.addSwitch('s1', dpid='0000000000000003', protocols='OpenFlow13')
    spine2 = net.addSwitch('s2', dpid='0000000000000004', protocols='OpenFlow13')
    spine3 = net.addSwitch('s3', dpid='0000000000000005', protocols='OpenFlow13')

    # 接入层交换机
    leaf1 = net.addSwitch('l1', dpid='0000000000000006', protocols='OpenFlow13')
    leaf2 = net.addSwitch('l2', dpid='0000000000000007', protocols='OpenFlow13')
    leaf3 = net.addSwitch('l3', dpid='0000000000000008', protocols='OpenFlow13')
    leaf4 = net.addSwitch('l4', dpid='0000000000000009', protocols='OpenFlow13')
    leaf5 = net.addSwitch('l5', dpid='0000000000000010', protocols='OpenFlow13')

    # 添加主机 - 外部网络
    info('*** 添加外部网络主机\n')
    h6 = net.addHost('h6', mac='00:00:00:00:00:06', ip='2001:db8:1::6/64')
    h7 = net.addHost('h7', mac='00:00:00:00:00:07', ip='2001:db8:1::7/64')
    h8 = net.addHost('h8', mac='00:00:00:00:00:08', ip='2001:db8:1::8/64')

    # 添加主机 - 数据中心网络
    info('*** 添加数据中心网络主机\n')
    # Leaf1连接的主机
    h1a = net.addHost('h1a', mac='00:00:00:00:01:01', ip='2001:db8:2:1::1/64')
    h1b = net.addHost('h1b', mac='00:00:00:00:01:02', ip='2001:db8:2:1::2/64')

    # Leaf2连接的主机
    h2a = net.addHost('h2a', mac='00:00:00:00:02:01', ip='2001:db8:2:2::1/64')
    h2b = net.addHost('h2b', mac='00:00:00:00:02:02', ip='2001:db8:2:2::2/64')

    # Leaf3连接的主机
    h3a = net.addHost('h3a', mac='00:00:00:00:03:01', ip='2001:db8:2:3::1/64')
    h3b = net.addHost('h3b', mac='00:00:00:00:03:02', ip='2001:db8:2:3::2/64')

    # Leaf4连接的主机
    h4a = net.addHost('h4a', mac='00:00:00:00:04:01', ip='2001:db8:2:4::1/64')
    h4b = net.addHost('h4b', mac='00:00:00:00:04:02', ip='2001:db8:2:4::2/64')

    # Leaf5连接的清洗服务器
    h5a = net.addHost('h5a', mac='00:00:00:00:05:01', ip='2001:db8:2:5::1/64')
    h5b = net.addHost('h5b', mac='00:00:00:00:05:02', ip='2001:db8:2:5::2/64')
    h5c = net.addHost('h5c', mac='00:00:00:00:05:03', ip='2001:db8:2:5::3/64')

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

    # 配置主机默认网关 - 与控制器中定义的网关IP匹配
    info('*** 配置默认网关\n')
    # 外部网络主机配置网关
    h6.cmd('ip -6 route add default via 2001:db8:1::ffff')
    h7.cmd('ip -6 route add default via 2001:db8:1::ffff')
    h8.cmd('ip -6 route add default via 2001:db8:1::ffff')

    # 数据中心网络主机配置网关
    h1a.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h1b.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h2a.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h2b.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h3a.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h3b.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h4a.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h4b.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h5a.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h5b.cmd('ip -6 route add default via 2001:db8:2::ffff')
    h5c.cmd('ip -6 route add default via 2001:db8:2::ffff')

    # 初始化邻居表
    info('*** 初始化主机邻居表\n')
    # 外部网络主机的网关邻居
    h6.cmd('ip -6 neigh add 2001:db8:1::ffff lladdr 00:00:00:00:00:f0 dev h6-eth0')
    h7.cmd('ip -6 neigh add 2001:db8:1::ffff lladdr 00:00:00:00:00:f0 dev h7-eth0')
    h8.cmd('ip -6 neigh add 2001:db8:1::ffff lladdr 00:00:00:00:00:f0 dev h8-eth0')

    # 数据中心网络主机的网关邻居
    h1a.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h1a-eth0')
    h1b.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h1b-eth0')
    h2a.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h2a-eth0')
    h2b.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h2b-eth0')
    h3a.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h3a-eth0')
    h3b.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h3b-eth0')
    h4a.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h4a-eth0')
    h4b.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h4b-eth0')
    h5a.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h5a-eth0')
    h5b.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h5b-eth0')
    h5c.cmd('ip -6 neigh add 2001:db8:2::ffff lladdr 00:00:00:00:00:f0 dev h5c-eth0')

    # 等待控制器连接
    info('*** 等待控制器连接\n')
    time.sleep(10)  # 保持10秒的等待时间

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