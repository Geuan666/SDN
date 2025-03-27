#!/bin/bash

# 检查Ryu控制器是否运行
check_ryu_running() {
    if pgrep -f "ryu-manager.*simple_switch.py" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# 如果没有参数，使用脚本拓扑
if [ $# -eq 0 ]; then
    if check_ryu_running; then
        echo "使用预配置拓扑连接到运行中的Ryu控制器..."
        python3 simple_topo.py
    else
        echo "错误: Ryu控制器未运行，请先运行run_network.sh"
        exit 1
    fi
else
    # 如果有参数，直接传递给mn命令但使用远程控制器
    if check_ryu_running; then
        echo "使用远程控制器模式启动Mininet..."
        mn --controller=remote,ip=127.0.0.1 "$@"
    else
        echo "错误: Ryu控制器未运行，请先运行run_network.sh"
        exit 1
    fi
fi 