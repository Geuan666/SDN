# 在VirtualBox中的Mininet-VM运行Ryu和Mininet Docker SDN实验环境

## 概述
由于Mininet依赖Linux内核的网络命名空间功能，无法直接在Windows系统上运行。本指南详细说明如何在VirtualBox的Mininet-VM虚拟机中运行Docker化的SDN实验环境。

## 先决条件
- 已安装VirtualBox
- 已安装Mininet-VM虚拟机
- Windows主机系统（已安装Docker Desktop用于其他用途）
- 项目文件已通过VirtualBox共享文件夹共享到虚拟机

## 安装步骤

### 1. 启动和配置Mininet-VM

#### 启动虚拟机
```bash
# 在VirtualBox中启动Mininet-VM
# 登录虚拟机（默认用户名/密码通常是mininet/mininet）
```

#### 配置Docker环境
```bash
# 更新系统包
sudo apt-get update

# 安装Docker
sudo apt-get install docker.io

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到docker组（避免每次使用sudo）
sudo usermod -aG docker $USER
newgrp docker

# 验证Docker安装
docker --version
```

#### 安装Make工具
```bash
sudo apt-get install make
```

#### 配置共享文件夹权限
```bash
# 将用户添加到VirtualBox共享文件夹组
sudo usermod -a -G vboxsf $USER
newgrp vboxsf

# 验证共享文件夹可访问
ls /media/sf_test-sdn
```

### 2. 运行项目

#### 切换到项目目录
```bash
cd /media/sf_test-sdn

# 确认项目文件存在
ls -la
```

#### 构建Docker镜像
```bash
# 使用make命令（推荐）
make build

# 或使用直接的Docker命令
docker build -t sdn-ryu-mininet .
```

#### 运行环境（选择一种方法）

**方法A：自动启动网络（推荐）**
```bash
make run-network
# 或使用Docker命令
docker run -it --rm --privileged -p 6633:6633 sdn-ryu-mininet ./run_network.sh auto
```

**方法B：交互式菜单模式**
```bash
# 使用make命令
make run-shell

# 在容器内执行
./run_network.sh

# 你会看到以下菜单：
# 1) 启动预设拓扑 (simple_topo.py)
# 2) 使用自定义mn命令 (--controller=remote)
# 3) 显示Ryu控制器日志
# 4) 停止Ryu控制器并退出
```

**方法C：使用docker-compose**
```bash
docker-compose up
```

**方法D：先启动控制器，再启动拓扑**
```bash
# 启动控制器
make run-ryu

# 在另一个终端启动拓扑
make run-mininet
```

**方法E：测试Docker环境**
```bash
./test-docker.sh
```

### 3. 验证和测试

#### 基本网络测试
```bash
# 在Mininet CLI中
mininet> pingall
mininet> h1 ping h4
mininet> iperf h1 h2
```

#### 查看流表
```bash
# 在新的VM终端中
docker exec -it <container_name> bash
ovs-ofctl dump-flows s1
```

## 故障排除

### 常见问题和解决方案

1. **权限问题**
   ```bash
   # 使用sudo临时解决
   sudo make build
   sudo make run-network
   
   # 或确保用户在正确的组中
   groups  # 检查当前用户组
   ```

2. **共享文件夹访问问题**
   ```bash
   # 检查共享文件夹挂载状态
   mount | grep sf_
   
   # 重新挂载共享文件夹
   sudo mount -t vboxsf test-sdn /media/sf_test-sdn
   ```

3. **Docker服务问题**
   ```bash
   # 检查Docker服务状态
   sudo systemctl status docker
   
   # 重启Docker服务
   sudo systemctl restart docker
   ```

4. **端口占用问题**
   ```bash
   # 清理之前的Mininet进程
   sudo mn -c
   
   # 检查端口使用情况
   sudo netstat -tulnp | grep 6633
   ```

## 清理环境

### 停止和清理容器
```bash
# 使用make命令
make stop
make clean

# 或手动清理
docker ps -a  # 查看所有容器
docker rm <container_id>
docker rmi sdn-ryu-mininet
```

### 清理Mininet
```bash
sudo mn -c
```

## 实验建议

1. **开始简单实验**
   - 测试基本网络连通性
   - 观察控制器日志
   - 理解流表操作

2. **修改和扩展**
   - 从simple_switch.py开始，理解基础控制器逻辑
   - 编辑custom_switch.py实现高级功能
   - 修改simple_topo.py创建新的网络拓扑
   - 实现QoS、防火墙等功能

3. **性能测试**
   - 使用iperf测试吞吐量
   - 分析延迟特性
   - 测试故障恢复机制

## 10. 项目文件详解

```
项目目录/
├── custom_switch.py       # 高级控制器框架（统计监控）
├── docker-compose.yml     # Docker Compose配置文件
├── Dockerfile             # Docker镜像构建文件
├── Makefile               # 便捷命令封装
├── README.md              # 项目说明文档
├── run_mininet.sh         # 单独启动Mininet脚本
├── run_network.sh         # 完整网络环境启动脚本
├── simple_switch.py       # 基础学习型交换机实现
├── simple_topo.py         # 预设网络拓扑（3交换机4主机）
├── start.sh               # Docker容器入口脚本
└── test-docker.sh         # Docker环境测试脚本
```

### 重要文件说明
- **控制器文件**：simple_switch.py（基础）和custom_switch.py（高级）
- **拓扑文件**：simple_topo.py定义网络结构
- **启动脚本**：run_network.sh是主要的启动脚本，支持交互式菜单
- **测试工具**：test-docker.sh用于验证环境配置

## 高级用法

### 使用docker-compose
```bash
# 直接使用docker-compose（项目已包含配置文件）
docker-compose up

# 或使用make命令
make compose-up
make compose-down

# 后台运行
docker-compose up -d
```

### 持久化数据
```bash
# 挂载外部目录到容器
docker run -it --rm --privileged \
  -v /media/sf_test-sdn:/workspace \
  -p 6633:6633 \
  sdn-ryu-mininet
```

## 注意事项

1. **内存限制**：确保虚拟机有足够内存（建议至少2GB）
2. **CPU虚拟化**：启用VirtualBox的硬件虚拟化支持
3. **网络配置**：使用桥接或NAT网络模式
4. **备份重要数据**：定期备份实验结果和代码修改

## 参考资源

- [Ryu官方文档](https://ryu.readthedocs.io/)
- [Mininet官方教程](http://mininet.org/walkthrough/)
- [OpenFlow规范](https://www.opennetworking.org/software-defined-standards/specifications/)

## 联系和支持

如果遇到问题，请检查：
1. Docker日志：`docker logs <container_id>`
2. Ryu日志：`tail -f ryu.log`
3. Mininet状态：`sudo mn --test pingall`

---
最后更新：2025年5月