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


class SimpleDCController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleDCController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.arp_table = {}  # IP -> MAC
        self.logger.info("数据中心控制器已启动")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 安装默认流表 - Table-miss
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        self.logger.info(f"交换机已连接: dpid={datapath.id}")

        # 初始化MAC表
        self.mac_to_port.setdefault(datapath.id, {})

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout)
        datapath.send_msg(mod)

    def _send_packet_out(self, datapath, buffer_id, in_port, out_port, data):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _handle_arp(self, datapath, in_port, pkt):
        # 提取ARP包
        pkt_arp = pkt.get_protocol(arp.arp)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)

        if pkt_arp.opcode == arp.ARP_REQUEST:
            # 记录源MAC和IP映射
            self.arp_table[pkt_arp.src_ip] = pkt_arp.src_mac
            self.logger.debug(f"学习ARP: {pkt_arp.src_ip} -> {pkt_arp.src_mac}")

            # 如果目标IP在ARP表中，直接回复
            if pkt_arp.dst_ip in self.arp_table:
                dst_mac = self.arp_table[pkt_arp.dst_ip]
                self.logger.debug(f"ARP响应: {pkt_arp.dst_ip} -> {dst_mac}")
                # 处理现有流表等...

        # 无论是否处理，都允许ARP包继续传播
        return False

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id

        # 解析数据包
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
                self.arp_table[arp_pkt.src_ip] = src_mac
                self.logger.debug(f"学习ARP: {arp_pkt.src_ip} -> {src_mac}")

        # 查找目标端口 - 如果找到MAC地址则使用，否则泛洪
        out_port = ofproto.OFPP_FLOOD
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
            self.logger.debug(f"找到目标端口: {dst_mac} -> {out_port}")

        # 构建动作
        actions = [parser.OFPActionOutput(out_port)]

        # 对单播包添加流表项以缓存MAC学习结果
        is_multicast = (dst_mac == 'ff:ff:ff:ff:ff:ff' or
                        dst_mac.startswith('01:00:5e') or
                        dst_mac.startswith('33:33'))

        if out_port != ofproto.OFPP_FLOOD and not is_multicast:
            # 为单播目的地添加流表
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst_mac)
            # 使用较短的超时以允许拓扑变化
            self.add_flow(datapath, 1, match, actions, idle_timeout=30)

        # 无论何种情况都发送当前包
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)