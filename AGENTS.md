## OpenClaw 插件本地部署

- OpenViking OpenClaw 插件源码位于 `examples/openclaw-plugin/`，是一个 context-engine 插件，运行在 OpenClaw 网关进程内部。
- **本地部署脚本**：`bot/scripts/install_local_openclaw_plugin.sh`，将插件源码同步到 `~/.openclaw/extensions/openviking/`，安装依赖、编译、并重启 OpenClaw 网关。
- 用法：在目标机器上 clone OpenViking 仓库并 checkout 到目标分支后，执行 `./bot/scripts/install_local_openclaw_plugin.sh`。
- `--rebuild` 参数：仅重新编译，不重新复制文件，适用于只改了 TypeScript 源码的场景。
- 插件本身不需要单独的服务进程；部署后重启 OpenClaw 网关即生效。
