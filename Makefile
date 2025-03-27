.PHONY: build run run-shell run-network run-ryu run-mininet stop clean logs help test compose-up compose-down compose-logs

# 镜像名称和容器名称
IMAGE_NAME = sdn-ryu-mininet
CONTAINER_NAME = sdn-network

# 默认目标
all: help

# 帮助信息
help:
	@echo "使用方法:"
	@echo "  make build         - 构建Docker镜像"
	@echo "  make run           - 运行完整环境（交互式shell）"
	@echo "  make run-shell     - 进入容器内部交互式shell"
	@echo "  make run-network   - 直接启动完整网络环境（自动选择选项1）"
	@echo "  make run-ryu       - 仅运行Ryu控制器"
	@echo "  make run-mininet   - 仅运行Mininet拓扑"
	@echo "  make stop          - 停止所有运行中的容器"
	@echo "  make logs          - 查看容器日志"
	@echo "  make clean         - 清理所有相关资源"
	@echo "  make test          - 运行基本测试"
	@echo ""
	@echo "Docker Compose命令:"
	@echo "  make compose-up    - 使用docker-compose启动所有服务"
	@echo "  make compose-down  - 使用docker-compose停止所有服务"
	@echo "  make compose-logs  - 查看docker-compose服务日志"

# 构建Docker镜像
build:
	@echo "构建Docker镜像..."
	docker build -t $(IMAGE_NAME) .
	@echo "构建完成: $(IMAGE_NAME)"

# 运行默认控制器和拓扑（交互式shell）
run:
	@echo "启动交互式环境..."
	docker run --rm -it \
		--name $(CONTAINER_NAME) \
		--privileged \
		-p 6633:6633 \
		-p 8080:8080 \
		$(IMAGE_NAME)

# 进入容器内部交互式shell
run-shell:
	@echo "进入容器内部交互式shell..."
	docker run --rm -it \
		--name $(CONTAINER_NAME)-shell \
		--privileged \
		-p 6633:6633 \
		-p 8080:8080 \
		-e TERM=xterm \
		$(IMAGE_NAME) bash

# 直接启动网络 - 自动选择选项1
run-network:
	@echo "直接启动网络环境..."
	-docker run --rm -it \
		--name $(CONTAINER_NAME) \
		--privileged \
		-p 6633:6633 \
		-p 8080:8080 \
		-e TERM=xterm \
		$(IMAGE_NAME) bash -c './run_network.sh auto; exit 0'
	@echo "网络环境已停止"

# 仅运行Ryu控制器
run-ryu:
	@echo "启动Ryu控制器..."
	docker run --rm -it \
		--name $(CONTAINER_NAME)-ryu \
		--privileged \
		-p 6633:6633 \
		-p 8080:8080 \
		$(IMAGE_NAME) ryu-manager --verbose simple_switch.py

# 仅运行Mininet拓扑（连接到独立运行的控制器）
run-mininet:
	@echo "启动Mininet拓扑..."
	docker run --rm -it \
		--name $(CONTAINER_NAME)-mininet \
		--privileged \
		-e TERM=xterm \
		-e CONTROLLER_IP=$(shell docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $(CONTAINER_NAME)-ryu 2>/dev/null || echo "127.0.0.1") \
		$(IMAGE_NAME) python3 simple_topo.py

# 查看容器日志
logs:
	docker logs $(CONTAINER_NAME) 2>/dev/null || echo "没有运行中的容器: $(CONTAINER_NAME)"

# 运行基本测试
test: build
	@echo "运行基本测试..."
	-docker run --rm -it \
		--name $(CONTAINER_NAME)-test \
		--privileged \
		$(IMAGE_NAME) /bin/bash -c "./run_network.sh auto && echo 'pingall' | mn -c; exit 0"
	@echo "测试完成"

# Docker Compose 命令
compose-up: build
	@echo "使用docker-compose启动所有服务..."
	docker-compose up -d

compose-down:
	@echo "使用docker-compose停止所有服务..."
	docker-compose down

compose-logs:
	@echo "查看docker-compose服务日志..."
	docker-compose logs -f

# 停止所有运行中的容器
stop:
	@echo "停止所有容器..."
	-docker stop $(CONTAINER_NAME) 2>/dev/null || true
	-docker stop $(CONTAINER_NAME)-shell 2>/dev/null || true
	-docker stop $(CONTAINER_NAME)-ryu 2>/dev/null || true
	-docker stop $(CONTAINER_NAME)-mininet 2>/dev/null || true
	@echo "所有容器已停止"

# 清理所有相关资源
clean: stop
	@echo "清理所有资源..."
	-docker rm $(CONTAINER_NAME) 2>/dev/null || true
	-docker rm $(CONTAINER_NAME)-shell 2>/dev/null || true
	-docker rm $(CONTAINER_NAME)-ryu 2>/dev/null || true
	-docker rm $(CONTAINER_NAME)-mininet 2>/dev/null || true
	-docker rmi $(IMAGE_NAME) 2>/dev/null || true
	@echo "清理完成" 