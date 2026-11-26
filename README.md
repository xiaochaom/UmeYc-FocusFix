# UmeYc-FocusFix

[English](README.en.md)

Steam Deck 的 Decky 插件，用于处理部分游戏进入场景后手柄和鼠标视角失效、重新聚焦窗口后恢复的问题。

插件跟随 Steam 界面语言。中文环境显示中文，其他语言环境显示英文。

## 使用

1. 在 Decky 设置中打开开发者模式，使用「从 ZIP 安装插件」选择 `UmeYc-FocusFix.zip`。
2. **崩坏：星穹铁道**右侧的开关默认关闭。启用后，插件从运行中的 Wine / Proton 进程定位前缀，从本次的 Unity 日志检测进图，每次启动尝试一次。打开开关后照常从 Steam 启动游戏。
3. **手动切换焦点**会关闭快捷菜单，并对当前游戏尝试一次失焦和重新聚焦。没有正在运行的游戏时，按钮置灰。关闭自动修复时仍可用手动按钮。
4. **自定义自动修复 → 添加或编辑规则**可以给其他游戏配置自动触发。选择 Steam 库中的游戏或非 Steam 快捷方式，通过文件选择器选中 `.log` 或 `.txt` 日志，再输入一段稳定的进图触发文字。插件按 UTF-8 原文匹配日志片段。每款游戏可单独启用、编辑或删除。

插件沿用 Steam 的游戏启动流程。崩铁预设会自行识别 Wine 前缀，检测到进图后在当前 Proton 会话里短暂显示 Win32 窗口，再把焦点交回游戏。手动按钮使用相同的 Win32 焦点切换，也支持通过 Gamescope 切换原生游戏的焦点。自定义规则需要游戏、日志和触发文字，保存后可重启游戏验证触发时机。

当前版本面向 SteamOS 游戏模式。自动触发要求能从运行进程识别对应的 Steam AppID，自定义日志须在用户主目录、`/run/media/<用户>` 或 `/mnt` 内。崩铁直启已在 Steam Deck 上验证日志触发，使用 Win32 弹窗后实测摇杆恢复。THRL Flatpak 等第三方启动器仍待验证。

## 构建

需要 Node.js、Python 3 和 MinGW-w64。默认编译器为 `x86_64-w64-mingw32-gcc`，使用 LLVM-MinGW 时可将 `FOCUSFIX_CC` 设为 `x86_64-w64-mingw32-clang`。

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm check
python3 -m unittest discover -s tests
pnpm package
```

安装包位于 `out/UmeYc-FocusFix.zip`。

## 鸣谢

- **zhh7ce** 提供了 Win32 焦点桥接方案和《崩坏：星穹铁道》的进图日志标记。本插件沿用该触发思路，在现有 Proton 会话中执行焦点切换。 [焦点桥接 Gist](https://gist.github.com/zhh7ce/a075e591cab7c3bd9066eb51d99b5892) · [崩铁配置](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-2088)
- **NEORUAA** 记录了失焦再聚焦后手柄和鼠标视角恢复的现象。**ericcccc21** 提供了 Steam Deck 游戏模式下打开「游戏工具」再返回的手动办法。**xiaochaom** 提交原始复现并验证了手动办法和 Gist 的焦点桥接。 [问题记录](https://dawn.wine/dawn-winery/dwproton/issues/44) · [焦点调查](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-1862) · [手动办法](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-2033) · [桥接实测](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-2089)
- 感谢 **Decky Loader** 和 **Valve Gamescope** 的开发者。 [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) · [Gamescope](https://github.com/ValveSoftware/gamescope)
