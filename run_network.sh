#!/bin/bash

# 定义全局变量
RYU_PID=0

# 检查是否有OpenVSwitch内核模块支持
check_ovs_modules() {
    echo "检查OpenVSwitch内核模块..."
    if lsmod | grep -q "openvswitch"; then
        echo "OpenVSwitch内核模块已加载"
        return 0
    else
        echo "尝试加载OpenVSwitch内核模块..."
        modprobe openvswitch || {
            echo "警告: 无法加载OpenVSwitch内核模块，可能影响功能"
            echo "如果在容器中运行，这可能是正常的，将继续尝试使用用户空间实现"
            return 1
        }
    fi
}

# 确保OVS服务正在运行
start_ovs_service() {
    echo "确保Open vSwitch服务正在运行..."
    service openvswitch-switch status > /dev/null 2>&1 || {
        echo "启动Open vSwitch服务..."
        service openvswitch-switch start
    }
}

# 清理可能存在的旧进程
clean_old_processes() {
    echo "清理可能存在的旧进程..."
    pkill -f ryu-manager || true
    pkill -f simple_topo.py || true
    mn -c > /dev/null 2>&1 || true
}

# 启动Ryu控制器
start_ryu_controller() {
    echo "启动Ryu控制器..."
    
    # 检查Ryu是否已安装
    if ! command -v ryu-manager &> /dev/null; then
        echo "错误: 找不到ryu-manager命令。请确保已正确安装Ryu控制器。"
        echo "推荐解决方案: "
        echo "  1. 检查Docker构建过程是否成功"
        echo "  2. 尝试手动运行: pip3 install ryu"
        exit 1
    fi
    
    # 检查控制器应用是否存在
    if [ ! -f "simple_switch.py" ]; then
        echo "错误: 找不到simple_switch.py控制器应用。"
        echo "推荐解决方案: 确保文件存在于当前目录"
        exit 1
    fi
    
    # 启动控制器，重定向输出到日志文件
    ryu-manager --verbose simple_switch.py > ryu.log 2>&1 &
    RYU_PID=$!

    # 检查控制器是否成功启动
    echo "等待Ryu控制器启动..."
    sleep 5
    if ! ps -p $RYU_PID > /dev/null; then
        echo "Ryu控制器启动失败，错误日志如下:"
        cat ryu.log
        echo ""
        echo "可能的解决方案:"
        echo "  1. 如果是依赖问题，检查Dockerfile中的pip3安装命令"
        echo "  2. 对于eventlet错误，尝试安装特定版本: pip3 install eventlet==0.30.2"
        echo "  3. 修改Dockerfile后重新构建Docker镜像"
        exit 1
    fi
    # 不显示PID值，避免被解释为退出码
    echo "Ryu控制器成功启动"
}

# 启动Mininet拓扑
start_mininet() {
    # 设置控制器IP为本地IP
    export CONTROLLER_IP="127.0.0.1"

    # 使用stty配置终端以便交互
    stty sane
    export TERM=xterm

    # 启动Mininet拓扑，前台运行
    echo "启动Mininet预设拓扑..."
    echo "注意: 当你输入'exit'或按Ctrl+D退出Mininet CLI后，网络将被停止"
    echo "-------------------------------------------------------------------"
    # 确保前台进程退出时返回正确的退出码
    python3 simple_topo.py
    # 保存退出码供后续使用
    local exit_code=$?
    return $exit_code
}

# 显示帮助菜单
show_menu() {
    echo ""
    echo "Ryu控制器已成功启动，请选择下一步操作:"
    echo "1) 启动预设拓扑 (simple_topo.py)"
    echo "2) 使用自定义mn命令 (--controller=remote)"
    echo "3) 显示Ryu控制器日志"
    echo "4) 停止Ryu控制器并退出"
    echo ""
    echo "请输入选项 [1-4]: "
}

# 处理用户选择
handle_choice() {
    local choice=$1
    case $choice in
        1)
            start_mininet
            ;;
        2)
            echo "请输入mn参数 (例如: --topo=tree,2), 或直接按Enter使用默认参数:"
            read mn_args
            echo "启动Mininet (mn --controller=remote,ip=127.0.0.1 $mn_args)..."
            mn --controller=remote,ip=127.0.0.1 $mn_args
            ;;
        3)
            echo "Ryu控制器日志:"
            echo "-------------------------------------------------------------------"
            cat ryu.log
            echo "-------------------------------------------------------------------"
            show_menu
            read choice
            handle_choice $choice
            ;;
        4)
            echo "停止Ryu控制器..."
            kill $RYU_PID || true
            wait $RYU_PID 2>/dev/null || true
            echo "网络环境已完全停止"
            ;;
        *)
            echo "无效选项，请重新选择"
            show_menu
            read choice
            handle_choice $choice
            ;;
    esac
}

# 主函数
main() {
    # 确保脚本总是返回0退出码
    trap 'exit 0' EXIT
    
    # 初始化环境
    check_ovs_modules
    start_ovs_service
    clean_old_processes
    
    # 启动控制器
    start_ryu_controller
    
    # 检查是否为自动模式
    if [ "$1" = "auto" ]; then
        echo "自动模式: 直接启动预设拓扑..."
        start_mininet
        
        # 当Mininet退出后，关闭Ryu控制器
        echo "停止Ryu控制器..."
        kill $RYU_PID || true
        wait $RYU_PID 2>/dev/null || true
        echo "网络环境已完全停止"
    else
        # 显示菜单并处理用户选择
        show_menu
        read choice
        handle_choice $choice
        
        # 如果用户选择了选项1或2，当Mininet退出后，关闭Ryu控制器
        if [ "$choice" = "1" ] || [ "$choice" = "2" ]; then
            echo "停止Ryu控制器..."
            kill $RYU_PID || true
            wait $RYU_PID 2>/dev/null || true
            echo "网络环境已完全停止"
        fi
    fi
    
    # 确保总是返回成功的退出码
    exit 0
}

# 执行主函数，传递第一个命令行参数
main "$1" 