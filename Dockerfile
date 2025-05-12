FROM ubuntu:20.04

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 添加镜像源(可选，如果网络不好可以使用)
# RUN sed -i 's/http:\/\/archive.ubuntu.com\/ubuntu\//http:\/\/mirrors.aliyun.com\/ubuntu\//g' /etc/apt/sources.list

# 安装必要的软件包
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    curl \
    wget \
    sudo \
    iputils-ping \
    iproute2 \
    tcpdump \
    net-tools \
    vim \
    iperf3 \
    openvswitch-switch \
    openvswitch-testcontroller \
    mininet \
    nano \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置pip配置，增加超时时间
RUN pip3 config set global.timeout 1000

# 首先安装特定版本的eventlet以解决兼容性问题
RUN pip3 install eventlet==0.30.2

# 单独安装每个包以增加成功率
RUN pip3 install six
RUN pip3 install webob
RUN pip3 install routes
RUN pip3 install msgpack-python
RUN pip3 install netaddr
RUN pip3 install oslo.config
RUN pip3 install ryu

# 确保mininet的Python模块可用
RUN if [ ! -d "/usr/lib/python3/dist-packages/mininet" ]; then \
        pip3 install mininet; \
    fi

# 安装OVS Python库
RUN pip3 install ovs
RUN pip3 install networkx

# 确保mnexec在PATH中
RUN if [ ! -f "/usr/local/bin/mnexec" ] && [ -f "/usr/bin/mnexec" ]; then \
        ln -s /usr/bin/mnexec /usr/local/bin/mnexec; \
    fi

# 用于验证mininet是否可导入
RUN python3 -c "import mininet; print('Mininet 已成功安装')"

# 设置工作目录
WORKDIR /root/sdn

# 复制项目文件
COPY . /root/sdn/

# 复制启动脚本（要放在 COPY . 之后，以免被覆盖）
COPY start.sh /start.sh
RUN chmod +x /start.sh

# 确保 run_network.sh 是可执行的
RUN chmod +x /root/sdn/run_network.sh
RUN chmod +x /root/sdn/run_datacenter_network.sh

# 暴露Ryu控制器端口
EXPOSE 6633 8080

# 容器启动命令
CMD ["/bin/bash"]