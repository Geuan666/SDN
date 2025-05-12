from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp
import ipaddress


class SimpleDatacenterController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleDatacenterController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.dpid_to_name = {}  # 用于日志记录
        self.router_mac = "00:00:00:00:00:f0"  # 虚拟路由器MAC
        self.edge_dpid = 2  # 边缘路由器DPID

        # 子网信息
        self.subnets = {
            "10.0.0.0/16": "外部网络",
            "10.1.0.0/16": "数据中心网络"
        }

        # 预设网关映射
        self.gateway_ips = {
            "10.0.0.0/16": "10.0.0.254",
            "10.1.0.0/16": "10.1.0.254"
        }

        # ARP表
        self.arp_table = {}

        self.logger.info("简化版数据中心控制器已启动")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 将DPID映射到更友好的名称
        dpid = datapath.id
        if dpid == 1:
            self.dpid_to_name[dpid] = "external_switch"
        elif dpid == 2:
            self.dpid_to_name[dpid] = "edge_router"
        elif dpid in [3, 4, 5]:
            self.dpid_to_name[dpid] = f"spine{dpid - 2}"
        elif dpid in [6, 7, 8, 9, 10]:
            self.dpid_to_name[dpid] = f"leaf{dpid - 5}"
        else:
            self.dpid_to_name[dpid] = f"switch{dpid}"

        # 初始化MAC表
        self.mac_to_port.setdefault(dpid, {})

        # 安装table-miss流表项
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info(f"交换机已连接: dpid={dpid} ({self.dpid_to_name[dpid]})")

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle_timeout=0):
        """向交换机添加流表项"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, idle_timeout=idle_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst,
                                    idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    def _get_subnet(self, ip):
        """获取IP地址所属子网"""
        try:
            ip_addr = ipaddress.ip_address(ip)
            for subnet in self.subnets:
                if ip_addr in ipaddress.ip_network(subnet):
                    return subnet
            return None
        except ValueError:
            return None

    def _is_same_subnet(self, ip1, ip2):
        """判断两个IP是否在同一子网"""
        subnet1 = self._get_subnet(ip1)
        subnet2 = self._get_subnet(ip2)
        if subnet1 and subnet2:
            return subnet1 == subnet2
        return False

    def _send_packet_out(self, datapath, buffer_id, in_port, actions, data=None):
        """发送数据包"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        if buffer_id == ofproto.OFP_NO_BUFFER:
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id,
                                      in_port=in_port, actions=actions, data=data)
        else:
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id,
                                      in_port=in_port, actions=actions)
        datapath.send_msg(out)

    def _build_arp_reply(self, datapath, in_port, eth_src, eth_dst, arp_src_mac, arp_dst_mac,
                         arp_src_ip, arp_dst_ip):
        """构建ARP响应包"""
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP,
                                           dst=eth_src, src=eth_dst))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
                                 src_mac=arp_dst_mac, src_ip=arp_dst_ip,
                                 dst_mac=arp_src_mac, dst_ip=arp_src_ip))
        pkt.serialize()

        actions = [datapath.ofproto_parser.OFPActionOutput(in_port)]
        self._send_packet_out(datapath, datapath.ofproto.OFP_NO_BUFFER,
                              datapath.ofproto.OFPP_CONTROLLER, actions, pkt.data)

        self.logger.info(f"发送ARP响应: {arp_dst_ip}({arp_dst_mac}) -> {arp_src_ip}({arp_src_mac})")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """处理交换机上报的数据包"""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id

        switch_name = self.dpid_to_name.get(dpid, f"dpid{dpid}")

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # 忽略LLDP包
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst_mac = eth.dst
        src_mac = eth.src

        # 学习MAC地址
        self.mac_to_port[dpid][src_mac] = in_port

        # 处理ARP包
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocol(arp.arp)
            if arp_pkt:
                # 记录ARP信息到表中
                self.arp_table[arp_pkt.src_ip] = arp_pkt.src_mac

                # 处理ARP请求
                if arp_pkt.opcode == arp.ARP_REQUEST:
                    # 1. 检查是否是网关ARP请求
                    if arp_pkt.dst_ip in ["10.0.0.254", "10.1.0.254"]:
                        self._build_arp_reply(datapath, in_port, src_mac, self.router_mac,
                                              arp_pkt.src_mac, self.router_mac,
                                              arp_pkt.src_ip, arp_pkt.dst_ip)
                        return

                    # 2. 如果目标IP在ARP表中，直接响应
                    if arp_pkt.dst_ip in self.arp_table:
                        dst_mac = self.arp_table[arp_pkt.dst_ip]
                        self._build_arp_reply(datapath, in_port, src_mac, dst_mac,
                                              arp_pkt.src_mac, dst_mac,
                                              arp_pkt.src_ip, arp_pkt.dst_ip)
                        return

        # 处理IPv4包
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip_pkt = pkt.get_protocol(ipv4.ipv4)
            if ip_pkt:
                # 记录IP-MAC映射
                self.arp_table[ip_pkt.src] = src_mac

                # 检查是否是跨子网通信
                src_subnet = self._get_subnet(ip_pkt.src)
                dst_subnet = self._get_subnet(ip_pkt.dst)

                # 如果是边缘路由器并且是跨子网通信
                if dpid == self.edge_dpid and src_subnet != dst_subnet:
                    # 如果目标IP在ARP表中
                    if ip_pkt.dst in self.arp_table:
                        dst_mac = self.arp_table[ip_pkt.dst]

                        # 如果知道目标主机端口
                        if dst_mac in self.mac_to_port[dpid]:
                            out_port = self.mac_to_port[dpid][dst_mac]

                            # 设置路由动作
                            actions = [
                                parser.OFPActionSetField(eth_src=self.router_mac),
                                parser.OFPActionSetField(eth_dst=dst_mac),
                                parser.OFPActionOutput(out_port)
                            ]

                            # 安装正向流表
                            match = parser.OFPMatch(
                                eth_type=ether_types.ETH_TYPE_IP,
                                ipv4_src=ip_pkt.src,
                                ipv4_dst=ip_pkt.dst
                            )
                            self.add_flow(datapath, 10, match, actions, idle_timeout=300)

                            # 安装反向流表
                            reverse_match = parser.OFPMatch(
                                eth_type=ether_types.ETH_TYPE_IP,
                                ipv4_src=ip_pkt.dst,
                                ipv4_dst=ip_pkt.src
                            )
                            reverse_actions = [
                                parser.OFPActionSetField(eth_src=self.router_mac),
                                parser.OFPActionSetField(eth_dst=src_mac),
                                parser.OFPActionOutput(in_port)
                            ]
                            self.add_flow(datapath, 10, reverse_match, reverse_actions, idle_timeout=300)

                            # 发送当前包
                            self._send_packet_out(datapath, msg.buffer_id, in_port,
                                                  actions, msg.data)
                            return
                        else:
                            # 目标MAC未知端口，洪泛
                            self.logger.info(f"目标MAC {dst_mac} 端口未知, 洪泛")
                            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                            self._send_packet_out(datapath, msg.buffer_id, in_port,
                                                  actions, msg.data)
                            return

        # 基本L2交换功能
        if dst_mac in self.mac_to_port[dpid]:
            # 已知目标端口，直接发送
            out_port = self.mac_to_port[dpid][dst_mac]
            self.logger.debug(f"{switch_name}: {src_mac}->{dst_mac} 从端口{in_port}到端口{out_port}")

            actions = [parser.OFPActionOutput(out_port)]

            # 安装流表
            match = parser.OFPMatch(eth_dst=dst_mac)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, buffer_id=msg.buffer_id, idle_timeout=300)
                return
            else:
                self.add_flow(datapath, 1, match, actions, idle_timeout=300)
        else:
            # 目标MAC未知，洪泛
            out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]

        # 发送包
        self._send_packet_out(datapath, msg.buffer_id, in_port, actions, msg.data)