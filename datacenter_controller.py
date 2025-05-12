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


class EnhancedDCController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(EnhancedDCController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.arp_table = {}  # IP -> MAC

        # 边缘路由器信息 - 在Ryu中dpid是整数类型的十六进制值
        self.edge_router_dpid = 0x2  # 十六进制表示，对应dpid='2'
        self.edge_router_mac = "00:00:00:00:00:ff"  # 边缘路由器虚拟MAC

        # 虚拟网关信息
        self.gateway_macs = {
            "10.0.0.254": self.edge_router_mac,  # 外部网络网关
            "10.1.0.254": self.edge_router_mac  # 数据中心网络网关
        }

        # 定义子网
        self.subnets = {
            "10.0.0.0/16": "外部网络",
            "10.1.0.0/16": "数据中心网络"
        }

        # 初始化ARP表，添加网关MAC地址
        for gateway_ip, mac in self.gateway_macs.items():
            self.arp_table[gateway_ip] = mac

        self.logger.info("增强版数据中心控制器已启动")
        self.logger.info(f"边缘路由器DPID: 0x{self.edge_router_dpid:x}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 输出交换机DPID信息，方便调试
        self.logger.info(f"交换机已连接: dpid=0x{datapath.id:x}")

        # 安装默认流表 - Table-miss
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    def _send_packet_out(self, datapath, buffer_id, in_port, actions, data=None):
        """发送数据包出端口"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        if buffer_id != ofproto.OFP_NO_BUFFER:
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id,
                                      in_port=in_port, actions=actions)
        else:
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                      in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    # 判断IP是否属于同一子网
    def is_in_same_subnet(self, ip1, ip2):
        try:
            for subnet in self.subnets:
                network = ipaddress.ip_network(subnet)
                ip1_obj = ipaddress.ip_address(ip1)
                ip2_obj = ipaddress.ip_address(ip2)
                if ip1_obj in network and ip2_obj in network:
                    return True
            return False
        except ValueError:
            self.logger.error(f"IP地址格式错误: {ip1} 或 {ip2}")
            return False

    # 获取IP所属子网
    def get_subnet_gateway(self, ip):
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj in ipaddress.ip_network("10.0.0.0/16"):
                return "10.0.0.254"
            elif ip_obj in ipaddress.ip_network("10.1.0.0/16"):
                return "10.1.0.254"
            return None
        except ValueError:
            self.logger.error(f"IP地址格式错误: {ip}")
            return None

    # 发送ARP请求
    def send_arp_request(self, datapath, src_mac, src_ip, dst_ip):
        """发送ARP请求以发现目标MAC地址"""
        self.logger.info(f"发送ARP请求: {src_ip}({src_mac}) 查询 {dst_ip}")

        # 构建ARP请求包
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_ARP,
            dst="ff:ff:ff:ff:ff:ff",  # 广播
            src=src_mac))

        pkt.add_protocol(arp.arp(
            opcode=arp.ARP_REQUEST,
            src_mac=src_mac,
            src_ip=src_ip,
            dst_mac="00:00:00:00:00:00",
            dst_ip=dst_ip))

        pkt.serialize()

        # 发送到所有端口
        actions = [datapath.ofproto_parser.OFPActionOutput(
            datapath.ofproto.OFPP_FLOOD)]
        self._send_packet_out(datapath, datapath.ofproto.OFP_NO_BUFFER,
                              in_port=datapath.ofproto.OFPP_CONTROLLER,
                              actions=actions, data=pkt.data)

    # 发送ARP响应
    def send_arp_reply(self, datapath, in_port, src_mac, dst_mac, src_ip, dst_ip):
        self.logger.info(f"发送ARP响应: {src_ip}({dst_mac}) -> {dst_ip}({src_mac})")

        # 构建ARP回复包
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_ARP,
            dst=src_mac,
            src=dst_mac))

        pkt.add_protocol(arp.arp(
            opcode=arp.ARP_REPLY,
            src_mac=dst_mac,
            src_ip=src_ip,
            dst_mac=src_mac,
            dst_ip=dst_ip))

        pkt.serialize()

        # 发送数据包
        actions = [datapath.ofproto_parser.OFPActionOutput(in_port)]
        self._send_packet_out(datapath, datapath.ofproto.OFP_NO_BUFFER,
                              in_port=datapath.ofproto.OFPP_CONTROLLER,
                              actions=actions, data=pkt.data)

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

        # 打印接收到的数据包信息（调试用）
        self.logger.debug(f"Packet in: dpid=0x{dpid:x} src_mac={src_mac} dst_mac={dst_mac} in_port={in_port}")

        # 特殊处理边缘路由器
        if dpid == self.edge_router_dpid:
            # 处理ARP包
            if eth_pkt.ethertype == ether_types.ETH_TYPE_ARP:
                arp_pkt = pkt.get_protocol(arp.arp)
                if arp_pkt:
                    # 学习ARP信息
                    self.arp_table[arp_pkt.src_ip] = arp_pkt.src_mac
                    self.logger.info(f"学习ARP: {arp_pkt.src_ip} -> {arp_pkt.src_mac}")

                    # 处理ARP请求
                    if arp_pkt.opcode == arp.ARP_REQUEST:
                        # 检查是否是针对网关的ARP请求
                        if arp_pkt.dst_ip in self.gateway_macs:
                            self.send_arp_reply(datapath, in_port,
                                                src_mac, self.gateway_macs[arp_pkt.dst_ip],
                                                arp_pkt.dst_ip, arp_pkt.src_ip)
                            return

                        # 检查是否是跨子网ARP请求
                        if not self.is_in_same_subnet(arp_pkt.src_ip, arp_pkt.dst_ip):
                            # 如果目标IP在ARP表中
                            if arp_pkt.dst_ip in self.arp_table:
                                # 发送ARP响应，提供真实目标MAC
                                dst_mac = self.arp_table[arp_pkt.dst_ip]
                                self.send_arp_reply(datapath, in_port,
                                                    src_mac, dst_mac,
                                                    arp_pkt.dst_ip, arp_pkt.src_ip)
                                return
                            else:
                                # 目标IP不在ARP表中，需要发送ARP请求到目标子网
                                gateway_ip = self.get_subnet_gateway(arp_pkt.dst_ip)
                                if gateway_ip:
                                    self.send_arp_request(datapath, self.edge_router_mac,
                                                          gateway_ip, arp_pkt.dst_ip)
                                    # 同时回复给请求方一个ARP响应，让它先发包到网关
                                    self.send_arp_reply(datapath, in_port,
                                                        src_mac, self.edge_router_mac,
                                                        arp_pkt.dst_ip, arp_pkt.src_ip)
                                    return

            # 处理IPv4包
            elif eth_pkt.ethertype == ether_types.ETH_TYPE_IP:
                ip_pkt = pkt.get_protocol(ipv4.ipv4)
                if ip_pkt:
                    # 记录IP到MAC的映射，以备后用
                    self.arp_table[ip_pkt.src] = src_mac

                    # 跨子网IPv4处理
                    if not self.is_in_same_subnet(ip_pkt.src, ip_pkt.dst):
                        self.logger.info(f"处理跨子网IPv4: {ip_pkt.src} -> {ip_pkt.dst}")

                        # 如果目标IP在ARP表中
                        if ip_pkt.dst in self.arp_table:
                            # 获取目标MAC
                            dst_mac = self.arp_table[ip_pkt.dst]

                            # 查找目标主机连接的端口
                            if dst_mac in self.mac_to_port[dpid]:
                                out_port = self.mac_to_port[dpid][dst_mac]

                                # 修改源MAC为路由器MAC，目标MAC为目标主机MAC
                                actions = [
                                    parser.OFPActionSetField(eth_src=self.edge_router_mac),
                                    parser.OFPActionSetField(eth_dst=dst_mac),
                                    parser.OFPActionOutput(out_port)
                                ]

                                # 下发流表
                                match = parser.OFPMatch(
                                    eth_type=ether_types.ETH_TYPE_IP,
                                    ipv4_src=ip_pkt.src,
                                    ipv4_dst=ip_pkt.dst
                                )
                                self.add_flow(datapath, 2, match, actions, idle_timeout=30)

                                # 发送当前数据包
                                self._send_packet_out(datapath, msg.buffer_id,
                                                      in_port, actions, data=msg.data)
                                return
                        else:
                            # 目标IP不在ARP表中，需要发送ARP请求
                            gateway_ip = self.get_subnet_gateway(ip_pkt.dst)
                            if gateway_ip:
                                self.send_arp_request(datapath, self.edge_router_mac,
                                                      gateway_ip, ip_pkt.dst)
                                # 暂时缓存这个数据包，等ARP应答后再转发
                                # (简化版实现中直接丢弃，实际应该缓存)
                                return

        # 普通交换机或未处理的情况 - 基本L2转发
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

        # 发送当前数据包
        self._send_packet_out(datapath, msg.buffer_id,
                              in_port, actions, data=msg.data)