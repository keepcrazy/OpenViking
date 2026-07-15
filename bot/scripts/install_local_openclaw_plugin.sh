#!/bin/bash
set -e

# 安装本地 OpenClaw OpenViking 插件
# 用法: ./install_local_openclaw_plugin.sh [--rebuild]
#
# 选项:
#   --rebuild   只重新编译，不重新复制文件

REBUILD=false
if [[ "$1" == "--rebuild" ]]; then
  REBUILD=true
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 源目录：openviking 根目录下的 examples/openclaw-plugin
OPENCLAW_PLUGIN_SOURCE="$(dirname "$SCRIPT_DIR")/../examples/openclaw-plugin"
OPENCLAW_PLUGIN_DIR="$HOME/.openclaw/extensions/openviking"

echo "=== 安装本地 OpenClaw OpenViking 插件 ==="
echo "源目录: $OPENCLAW_PLUGIN_SOURCE"
echo "目标目录: $OPENCLAW_PLUGIN_DIR"

# 检查源目录是否存在
if [[ ! -d "$OPENCLAW_PLUGIN_SOURCE" ]]; then
  echo "错误: 源目录不存在: $OPENCLAW_PLUGIN_SOURCE"
  exit 1
fi

# 删除旧的插件目录
if [[ "$REBUILD" == "false" ]]; then
  echo "删除旧插件目录..."
  rm -rf "$OPENCLAW_PLUGIN_DIR"

  # 复制插件源码，但绝不复制本地 node_modules（其中的 .bin 符号链接
  # 在复制后会失效），依赖必须在目标目录重新安装。
  echo "复制源文件（跳过 node_modules 和构建产物）..."
  mkdir -p "$OPENCLAW_PLUGIN_DIR"
  rsync -a --exclude node_modules --exclude dist \
    "$OPENCLAW_PLUGIN_SOURCE/" "$OPENCLAW_PLUGIN_DIR/"

  # 安装干净的开发依赖，确保 tsc/vitest 可用。
  echo "安装依赖..."
  cd "$OPENCLAW_PLUGIN_DIR"
  npm ci --include=dev
fi

# 编译运行产物。tsconfig.json 仅用于类型检查（noEmit），必须使用 build 脚本生成 dist/。
echo "编译 TypeScript 运行产物..."
cd "$OPENCLAW_PLUGIN_DIR"
npm run build

if [[ ! -f "$OPENCLAW_PLUGIN_DIR/dist/index.js" ]]; then
  echo "错误: 编译未生成 dist/index.js，终止重启。"
  exit 1
fi

# 重启 OpenClaw
echo "重启 OpenClaw..."
if command -v openclaw &> /dev/null; then
  openclaw gateway restart
  sleep 2
  echo ""
  echo "=== 等待插件加载，按 Ctrl+C 退出日志 ==="
  openclaw logs --follow | grep -E "openviking|context-engine|error.*plugin" | head -10
else
  echo "警告: openclaw 命令未找到，请手动重启 OpenClaw"
fi