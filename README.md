# Ryu和Mininet SDN实验环境

本项目提供了一个完整的Docker化SDN实验环境，集成了Ryu控制器和Mininet网络模拟器，便于快速部署和测试SDN网络应用。

## 环境要求

- Docker
- Make (可选，用于简化命令)
- docker-compose (可选，用于管理多容器服务)

## 快速开始

### 构建Docker镜像

```bash
make build
```

或者直接使用Docker命令:

```bash
docker build -t sdn-ryu-mininet .
```

### 运行环境

您可以通过以下几种方式运行环境:

1. **直接启动网络** (推荐) - 自动启动控制器和预设拓扑:

```bash
make run-network
```

2. **进入交互式Shell** - 进入容器后需手动启动服务:

```bash
make run-shell
```

进入容器后，执行以下命令来启动网络(将显示菜单):

```bash
./run_network.sh
```

3. **自定义环境** - 进入容器但不启动任何服务:

```bash
make run
```

### 使用Docker Compose (推荐)

如果您安装了docker-compose，可以一键启动整个环境:

```bash
make compose-up
```

### 分离式运行 (适用于多机部署)

#### 仅运行Ryu控制器

```bash
make run-ryu
```

#### 仅运行Mininet拓扑 (连接到独立运行的控制器)

```bash
make run-mininet
```

> 注意: 如果先运行控制器再运行Mininet，系统会自动检测控制器IP并连接。

## 容器内使用Mininet

在容器内有两种方式使用Mininet:

### 1. 使用预置的拓扑脚本（推荐）

在Ryu控制器启动后，运行:

```bash
python3 simple_topo.py
```

这将启动预定义的拓扑并连接到运行中的控制器。

### 2. 使用mn命令

直接运行`mn`命令会尝试启动自带的控制器，与Ryu控制器端口冲突。正确的做法是:

```bash
# 使用远程控制器模式
mn --controller=remote,ip=127.0.0.1
```

或者使用我们提供的辅助脚本:

```bash
# 不带参数，启动预定义拓扑
./run_mininet.sh

# 带参数，使用远程控制器启动自定义拓扑
./run_mininet.sh --topo=tree,2
```

> 注意：必须先运行run_network.sh或启动Ryu控制器，才能使用Mininet。

## 项目文件说明

- `Dockerfile`: 定义Docker镜像构建过程
- `Makefile`: 提供方便的命令封装
- `start.sh`: Docker容器的入口点脚本
- `run_network.sh`: 在容器内同时启动Ryu和Mininet的脚本
- `run_mininet.sh`: 辅助脚本，用于在控制器启动后正确运行Mininet
- `simple_switch.py`: Ryu控制器的简单交换机应用
- `simple_topo.py`: Mininet的示例网络拓扑
- `docker-compose.yml`: 定义多容器服务配置

## 命令说明

| 命令 | 描述 |
|------|------|
| `make build` | 构建Docker镜像 |
| `make run-network` | 直接启动网络（自动运行控制器和预设拓扑） |
| `make run-shell` | 进入容器交互式Shell（需手动运行网络） |
| `make run` | 进入容器（不启动任何服务） |
| `make run-ryu` | 仅启动Ryu控制器 |
| `make run-mininet` | 仅启动Mininet拓扑 |
| `make compose-up` | 使用docker-compose启动所有服务 |
| `make compose-down` | 停止docker-compose服务 |
| `make stop` | 停止所有容器 |
| `make clean` | 清理所有资源 |
| `make help` | 显示帮助信息 |

## 测试网络连通性

在Mininet CLI中，可以通过以下命令测试网络连通性:

```
mininet> pingall
```

或者测试特定主机之间的连通性:

```
mininet> h1 ping h4
```

## 自定义开发

1. 修改`simple_switch.py`以实现自定义控制器逻辑
2. 修改`simple_topo.py`以创建不同的网络拓扑
3. 重新构建并运行环境进行测试

## 网络拓扑说明

默认拓扑创建了一个包含3个交换机和4个主机的网络:

```
h1 --- s1 --- s2 --- s3 --- h4
        |      |
        |      |
       h2     h3
```

所有主机都在同一子网 (10.0.0.0/24)。

## 常见问题解决

- **权限问题**: 确保使用`--privileged`参数运行Docker容器
- **控制器连接失败**: 检查端口映射和网络设置，查看ryu.log获取错误详情
- **网络延迟**: 可以在`run_network.sh`中增加控制器等待时间
- **Docker网络问题**: 某些系统可能需要调整Docker网络设置，允许容器之间通信
- **OVS服务**: 如果Open vSwitch服务启动失败，检查系统兼容性和内核模块
- **Ryu依赖问题**: 如果遇到类似`ImportError: cannot import name 'ALREADY_HANDLED'`的错误，这是由于eventlet版本不兼容导致。项目已在Dockerfile中固定eventlet==0.30.2以解决此问题。
- **Mininet CLI不显示**: 如果进入容器后不显示Mininet CLI，请确保使用`-it`参数运行容器，并设置正确的终端环境变量
- **mn命令冲突**: 不要直接运行`mn`命令，它会启动自己的控制器导致端口冲突。使用`./run_mininet.sh`或正确指定远程控制器
- **run-network只进入容器**: 使用新版本的`make run-network`命令，它会自动启动网络，而`make run-shell`才是进入容器

## 高级用法

### 自定义控制器IP

```bash
CONTROLLER_IP=192.168.1.100 make run-mininet
```

### 运行多个控制器实例

修改端口映射可以运行多个控制器:

```bash
docker run --rm -it --name sdn-controller-1 --privileged -p 6634:6633 -p 8081:8080 sdn-ryu-mininet ryu-manager simple_switch.py
```

### 版本兼容性说明

本环境中使用了以下关键软件版本:

- Ubuntu 20.04 作为基础镜像
- Python 3.8 (Ubuntu 20.04默认版本)
- Ryu 最新版本
- eventlet 0.30.2 (为解决与Ryu的兼容性问题)
- Mininet 最新版本

如需使用其他版本，请修改Dockerfile并重新构建镜像。 