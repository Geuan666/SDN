from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class HubController(app_manager.RyuApp):
    """
    简单的集线器控制器 - 总是泛洪数据包
    为数据中心网络提供最基本的连通性
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(HubController, self).__init__(*args, **kwargs)
        self.logger.info("集线器控制器已启动")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 安装Table-miss流表 - 所有数据包发送到控制器
        match = parser.OFPMatch()  # 匹配所有数据包
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info(f"交换机已连接: dpid={datapath.id}")

    def add_flow(self, datapath, priority, match, actions):
        """添加流表项到交换机"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 将actions构建成指令
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        # 创建流表修改消息
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        # 发送消息到交换机
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """处理收到的数据包: 简单地泛洪每个数据包"""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # 解析数据包
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # 忽略LLDP包
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # 简单记录数据包信息
        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.logger.debug(f"Packet in dpid={dpid}: {src} -> {dst} from port {in_port}")

        # 无论目的地址如何，始终泛洪所有数据包
        out_port = ofproto.OFPP_FLOOD
        actions = [parser.OFPActionOutput(out_port)]

        # 如果有缓冲ID，使用它；否则，包含完整数据
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        # 创建输出消息并发送
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)