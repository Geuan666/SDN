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
from ryu.lib.packet import icmp
import ipaddress


class ARPProxy:
    """
    ARP代理类：处理跨子网ARP请求并返回路由器MAC地址
    """

    def __init__(self, logger):
        self.logger = logger
        self.arp_table = {}  # 存储IP到MAC的映射

        # 路由器MAC地址
        self.router_mac = "00:00:00:00:ff:01"

        # 定义子网
        self.subnets = {
            "10.0.0.0/16": "外部网络",
            "10.1.0.0/16": "数据中心内部网络"
        }

    def _get_subnet_for_ip(self, ip):
        """确定IP地址所属的子网"""
        ip_obj = ipaddress.ip_address(ip)
        for subnet in self.subnets:
            if ip_obj in ipaddress.ip_network(subnet):
                return subnet
        return None

    def _are_ip_in_same_subnet(self, ip1, ip2):
        """判断两个IP是否在同一子网"""
        subnet1 = self._get_subnet_for_ip(ip1)
        subnet2 = self._get_subnet_for_ip(ip2)
        return subnet1 == subnet2

    def learn_arp_entry(self, ip, mac):
        """学习ARP表条目"""
        self.arp_table[ip] = mac
        self.logger.debug(f"ARP代理：学习ARP条目 {ip} -> {mac}")
        return True

    def get_mac_for_ip(self, ip):
        """获取IP对应的MAC地址"""
        return self.arp_table.get(ip, None)

    def create_arp_reply(self, arp_req):
        """
        创建ARP回复数据包
        arp_req: 原始ARP请求
        """
        pkt = packet.Packet()

        # 查看请求和目标是否在同一子网
        if not self._are_ip_in_same_subnet(arp_req.src_ip, arp_req.dst_ip):
            # 跨子网请求，返回路由器MAC
            reply_mac = self.router_mac
            self.logger.info(f"ARP代理：跨子网请求 {arp_req.src_ip}->{arp_req.dst_ip}，返回路由器MAC")
        elif arp_req.dst_ip in self.arp_table:
            # 同子网且目标IP已知，返回实际MAC
            reply_mac = self.arp_table[arp_req.dst_ip]
            self.logger.info(f"ARP代理：同子网请求 {arp_req.src_ip}->{arp_req.dst_ip}，返回已知MAC")
        else:
            # 同子网但目标未知，无法响应
            return None

        # 构建以太网头
        eth_hdr = ethernet.ethernet(
            dst=arp_req.src_mac,
            src=reply_mac,
            ethertype=ether_types.ETH_TYPE_ARP
        )

        # 构建ARP回复
        arp_reply = arp.arp(
            hwtype=1, proto=0x0800, hlen=6, plen=4,
            opcode=arp.ARP_REPLY,
            src_mac=reply_mac,
            src_ip=arp_req.dst_ip,
            dst_mac=arp_req.src_mac,
            dst_ip=arp_req.src_ip
        )

        pkt.add_protocol(eth_hdr)
        pkt.add_protocol(arp_reply)
        pkt.serialize()

        return pkt.data

    def handle_arp_packet(self, datapath, in_port, pkt):
        """
        处理ARP数据包
        返回：(需要处理, 输出包数据, 输出端口)
        """
        arp_pkt = pkt.get_protocol(arp.arp)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)

        # 学习源IP和MAC
        self.learn_arp_entry(arp_pkt.src_ip, arp_pkt.src_mac)

        # 如果是ARP请求
        if arp_pkt.opcode == arp.ARP_REQUEST:
            # 创建ARP回复
            reply_data = self.create_arp_reply(arp_pkt)
            if reply_data:
                # 返回需要处理标志，回复数据，输出端口
                return (True, reply_data, datapath.ofproto.OFPP_IN_PORT)

        # 默认不处理
        return (False, None, None)


class EnhancedDCController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(EnhancedDCController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.arp_table = {}  # IP -> MAC
        self.dp_to_dpid = {}  # Datapath -> DPID

        # 初始化ARP代理
        self.arp_proxy = ARPProxy(self.logger)

        # 定义网关和网段映射
        self.router_mac = "00:00:00:00:ff:01"  # 边缘路由器的虚拟MAC

        # 子网信息
        self.subnets = {
            "10.0.0.0/16": "外部网络",
            "10.1.0.0/16": "数据中心网络"
        }

        # 边缘路由器信息
        self.edge_router_dpid = 2  # ed的dpid值

        self.logger.info("增强版数据中心控制器已启动")

    def _get_subnet_for_ip(self, ip):
        """确定IP地址所属的子网"""
        ip_obj = ipaddress.ip_address(ip)
        for subnet in self.subnets:
            if ip_obj in ipaddress.ip_network(subnet):
                return subnet
        return None

    def _are_ip_in_same_subnet(self, ip1, ip2):
        """判断两个IP是否在同一子网"""
        subnet1 = self._get_subnet_for_ip(ip1)
        subnet2 = self._get_subnet_for_ip(ip2)
        return subnet1 == subnet2

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 存储DPID映射
        self.dp_to_dpid[datapath.id] = datapath

        # 安装默认流表 - Table-miss
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info(f"交换机已连接: dpid={datapath.id}")

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    def _send_packet_out(self, datapath, in_port, out_port, data):
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _send_arp_reply(self, datapath, in_port, arp_req, reply_mac):
        """发送ARP回复"""
        eth_pkt = packet.Packet()

        # 构建以太网头
        eth_hdr = ethernet.ethernet(dst=arp_req.src_mac,
                                    src=reply_mac,
                                    ethertype=ether_types.ETH_TYPE_ARP)

        # 构建ARP回复
        arp_reply = arp.arp(hwtype=1, proto=0x0800, hlen=6, plen=4,
                            opcode=arp.ARP_REPLY,
                            src_mac=reply_mac,
                            src_ip=arp_req.dst_ip,
                            dst_mac=arp_req.src_mac,
                            dst_ip=arp_req.src_ip)

        eth_pkt.add_protocol(eth_hdr)
        eth_pkt.add_protocol(arp_reply)
        eth_pkt.serialize()

        self._send_packet_out(datapath, in_port, datapath.ofproto.OFPP_IN_PORT, eth_pkt.data)
        self.logger.debug(f"发送ARP应答: {arp_req.dst_ip} --> {arp_req.src_ip}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id

        # 确保该交换机有一个MAC表条目
        self.mac_to_port.setdefault(dpid, {})

        # 提取数据包信息
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)

        if not eth_pkt:
            return

        # 忽略LLDP包
        if eth_pkt.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst_mac = eth_pkt.dst
        src_mac = eth_pkt.src

        # 学习源MAC和端口
        self.mac_to_port[dpid][src_mac] = in_port

        # 处理ARP包
        if eth_pkt.ethertype == ether_types.ETH_TYPE_ARP:
            arp_pkt = pkt.get_protocol(arp.arp)
            if arp_pkt:
                # 使用ARP代理处理
                handled, reply_data, out_port = self.arp_proxy.handle_arp_packet(datapath, in_port, pkt)
                if handled:
                    self._send_packet_out(datapath, in_port, out_port, reply_data)
                    return

        # 处理IPv4包
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst
            self.logger.debug(f"IPv4数据包: {src_ip} -> {dst_ip}")

            # 检查跨子网通信
            if not self._are_ip_in_same_subnet(src_ip, dst_ip):
                self.logger.info(f"跨子网通信: {src_ip} -> {dst_ip}")

                # 如果当前交换机是边缘路由器，处理路由逻辑
                if dpid == self.edge_router_dpid:
                    # 尝试获取目标MAC
                    if dst_ip in self.arp_table:
                        dst_mac = self.arp_table[dst_ip]
                        if dst_mac in self.mac_to_port[dpid]:
                            out_port = self.mac_to_port[dpid][dst_mac]
                            actions = [parser.OFPActionOutput(out_port)]

                            # 安装流表
                            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                                    ipv4_src=src_ip, ipv4_dst=dst_ip)
                            self.add_flow(datapath, 1, match, actions, idle_timeout=30)

                            # 转发当前包
                            data = None
                            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                                data = msg.data

                            out = parser.OFPPacketOut(
                                datapath=datapath, buffer_id=msg.buffer_id,
                                in_port=in_port, actions=actions, data=data)
                            datapath.send_msg(out)
                            return

        # 决定输出端口
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        # 构建动作
        actions = [parser.OFPActionOutput(out_port)]

        # 安装流表 (仅对非泛洪)
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac)
            self.add_flow(datapath, 1, match, actions, idle_timeout=30)

        # 无论如何，都转发当前包
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)