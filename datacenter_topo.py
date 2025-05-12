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

class LinuxRouter( Node ):
    "A Node with IP forwarding enabled."

    def config( self, **params ):
        super( LinuxRouter, self ).config( **params )
        # 开启 IP 转发
        self.cmd( 'sysctl -w net.ipv4.ip_forward=1' )

    def terminate( self ):
        self.cmd( 'sysctl -w net.ipv4.ip_forward=0' )
        super( LinuxRouter, self ).terminate()


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
    external_switch = net.addSwitch('ex', dpid='0000000000000001',protocols='OpenFlow13')

    # 添加交换机 - 数据中心网络
    info('*** 添加数据中心网络交换机\n')
    # 边缘路由器 - 确保dpid为2，与控制器中的edge_router_dpid=2一致
    edge_router = net.addSwitch('ed', dpid='0000000000000002',protocols='OpenFlow13')

    # 汇聚层交换机
    spine1 = net.addSwitch('s1', dpid='0000000000000003',protocols='OpenFlow13')
    spine2 = net.addSwitch('s2', dpid='0000000000000004',protocols='OpenFlow13')
    spine3 = net.addSwitch('s3', dpid='0000000000000005',protocols='OpenFlow13')

    # 接入层交换机
    leaf1 = net.addSwitch('l1', dpid='0000000000000006',protocols='OpenFlow13')
    leaf2 = net.addSwitch('l2', dpid='0000000000000007',protocols='OpenFlow13')
    leaf3 = net.addSwitch('l3', dpid='0000000000000008',protocols='OpenFlow13')
    leaf4 = net.addSwitch('l4', dpid='0000000000000009',protocols='OpenFlow13')
    leaf5 = net.addSwitch('l5', dpid='0000000000000010',protocols='OpenFlow13')

    # 添加主机 - 外部网络 (使用/16掩码，与控制器中的10.0.0.0/16匹配)
    info('*** 添加外部网络主机\n')
    h6 = net.addHost('h6', mac='00:00:00:00:00:06', ip='10.0.6.1/16')
    h7 = net.addHost('h7', mac='00:00:00:00:00:07', ip='10.0.7.1/16')
    h8 = net.addHost('h8', mac='00:00:00:00:00:08', ip='10.0.8.1/16')

    # 添加主机 - 数据中心网络 (使用/16掩码，与控制器中的10.1.0.0/16匹配)
    info('*** 添加数据中心网络主机\n')
    # Leaf1连接的主机
    h1a = net.addHost('h1a', mac='00:00:00:00:01:01', ip='10.1.1.1/16')
    h1b = net.addHost('h1b', mac='00:00:00:00:01:02', ip='10.1.1.2/16')

    # Leaf2连接的主机
    h2a = net.addHost('h2a', mac='00:00:00:00:02:01', ip='10.1.2.1/16')
    h2b = net.addHost('h2b', mac='00:00:00:00:02:02', ip='10.1.2.2/16')

    # Leaf3连接的主机
    h3a = net.addHost('h3a', mac='00:00:00:00:03:01', ip='10.1.3.1/16')
    h3b = net.addHost('h3b', mac='00:00:00:00:03:02', ip='10.1.3.2/16')

    # Leaf4连接的主机
    h4a = net.addHost('h4a', mac='00:00:00:00:04:01', ip='10.1.4.1/16')
    h4b = net.addHost('h4b', mac='00:00:00:00:04:02', ip='10.1.4.2/16')

    # Leaf5连接的清洗服务器
    h5a = net.addHost('h5a', mac='00:00:00:00:05:01', ip='10.1.5.1/16')
    h5b = net.addHost('h5b', mac='00:00:00:00:05:02', ip='10.1.5.2/16')
    h5c = net.addHost('h5c', mac='00:00:00:00:05:03', ip='10.1.5.3/16')

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

    info('*** 添加路由器节点\n')
    # 路由器0：承载外部网络网关 10.0.0.254/16，连接到 external_switch
    r0 = net.addHost('r0', cls=LinuxRouter,
                     ip='10.0.0.254/16',
                     mac='00:00:00:00:00:ff')
    r1 = net.addHost('r1', cls=LinuxRouter,
                     ip='10.1.0.254/16',
                     mac='00:00:00:00:00:ff')

    info('*** 在路由器和交换机之间添加链路\n')
    net.addLink(r0, external_switch)
    net.addLink(r1, edge_router)

    # 添加 r0–r1 直连链路，使用 10.254.0.0/30
    info('*** 添加路由器互联链路\n')
    net.addLink( r0, r1, intfName1='r0-eth2', intfName2='r1-eth2' )

    # 启动网络
    info('*** 启动网络\n')
    net.build()
    c0.start()

    # 分配直连子接口 IP
    r0.cmd('ifconfig r0-eth2 10.254.0.1/30')
    r1.cmd('ifconfig r1-eth2 10.254.0.2/30')

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
    # 外部网络主机配置网关 - 10.0.0.254 (与控制器中的 self.gateway_macs 匹配)
    h6.cmd('ip route add default via 10.0.0.254')
    h7.cmd('ip route add default via 10.0.0.254')
    h8.cmd('ip route add default via 10.0.0.254')

    # 数据中心网络主机配置网关 - 10.1.0.254 (与控制器中的 self.gateway_macs 匹配)
    h1a.cmd('ip route add default via 10.1.0.254')
    h1b.cmd('ip route add default via 10.1.0.254')
    h2a.cmd('ip route add default via 10.1.0.254')
    h2b.cmd('ip route add default via 10.1.0.254')
    h3a.cmd('ip route add default via 10.1.0.254')
    h3b.cmd('ip route add default via 10.1.0.254')
    h4a.cmd('ip route add default via 10.1.0.254')
    h4b.cmd('ip route add default via 10.1.0.254')
    h5a.cmd('ip route add default via 10.1.0.254')
    h5b.cmd('ip route add default via 10.1.0.254')
    h5c.cmd('ip route add default via 10.1.0.254')
    r0.cmd( 'ip route add 10.1.0.0/16 via 10.254.0.2' )
    r1.cmd( 'ip route add 10.0.0.0/16 via 10.254.0.1' )

    # 等待控制器连接
    info('*** 等待控制器连接\n')
    time.sleep(5)

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