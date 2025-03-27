#!/bin/bash

# 检查Docker镜像是否存在
if ! sudo docker images | grep -q sdn-ryu-mininet; then
    echo "错误: sdn-ryu-mininet镜像不存在，请先构建镜像"
    exit 1
fi

# 测试1: 尝试进入交互式环境
echo "测试1: 进入容器交互式环境并显示帮助信息..."
sudo docker run --rm -it --privileged sdn-ryu-mininet bash -c "echo '显示控制器版本信息:' && ryu-manager --version && echo '测试通过'"

# 测试2: 检查必要的工具是否存在
echo "测试2: 检查控制器和Mininet是否正确安装..."
sudo docker run --rm -it --privileged sdn-ryu-mininet bash -c "command -v ryu-manager && command -v mn && echo '测试通过'"

echo "所有测试完成!" 