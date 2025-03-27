#!/bin/bash

# 启动Open vSwitch服务
service openvswitch-switch start

# 执行参数或进入bash
if [ $# -eq 0 ]; then
    echo "没有指定参数，进入bash"
    /bin/bash
else
    echo "执行命令: $@"
    exec "$@"
fi 