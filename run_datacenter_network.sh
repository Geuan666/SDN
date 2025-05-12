#!/bin/bash

# 定义全局变量
RYU_PID=0

# 清理可能存在的旧进程
echo "清理旧进程..."
pkill -f ryu-manager || true
pkill -f datacenter_topo.py || true
mn -c > /dev/null 2>&1 || true

# 确保OVS服务正在运行
echo "启动Open vSwitch服务..."
service openvswitch-switch start

# 启动Ryu控制器
echo "启动简化版数据中心控制器..."
ryu-manager --verbose datacenter_controller.py > datacenter_ryu.log 2>&1 &
RYU_PID=$!

# 检查控制器是否成功启动
echo "等待控制器启动..."
sleep 6  # 增加等待时间，确保控制器完全启动
if ! ps -p $RYU_PID > /dev/null; then
    echo "控制器启动失败!"
    cat datacenter_ryu.log  # 确保日志文件名称一致
    exit 1
fi
echo "控制器已启动!"

# 设置控制器IP为本地IP
export CONTROLLER_IP="127.0.0.1"

# 使用stty配置终端以便交互
stty sane
export TERM=xterm

# 启动Mininet拓扑
echo "启动数据中心拓扑..."
python3 datacenter_topo.py

# 清理
echo "停止控制器..."
kill $RYU_PID || true
wait $RYU_PID 2>/dev/null || true
echo "环境已停止"