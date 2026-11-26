const zh = {
  starRail: "崩坏：星穹铁道",
  automatic: "自动修复",
  manual: "手动切换焦点",
  loadFailed: "无法读取设置",
  autoSaveFailed: "无法保存自动修复设置",
  manualFailed: "无法切换当前游戏的焦点",
  customRules: "自定义自动修复",
  toggleFailed: "无法保存开关",
  editRule: "添加或编辑规则",
  game: "游戏",
  selectGame: "选择游戏",
  gameListUnavailable: "游戏列表不可用。启动游戏后可在这里选择。",
  logFile: "日志文件",
  selectLog: "选择日志文件",
  marker: "触发行",
  saveFailed: "无法保存。请选择有效的日志文件，并填写一行触发文字。",
  saveRule: "保存规则",
  deleteFailed: "无法删除规则",
  deleteRule: "删除规则",
  back: "返回",
  focus: {
    success: "已切换焦点并返回游戏",
    not_foreground: "请先返回运行中的游戏，再打开插件操作",
    unavailable: "当前 Gamescope 会话无法切换焦点",
    unconfirmed: "Gamescope 未确认焦点已完成切换",
    cancelled: "焦点切换已取消",
  },
};

const en: typeof zh = {
  starRail: "Honkai: Star Rail",
  automatic: "Automatic fix",
  manual: "Cycle game focus",
  loadFailed: "Could not load settings",
  autoSaveFailed: "Could not save the automatic fix setting",
  manualFailed: "Could not switch focus for the current game",
  customRules: "Custom automatic fixes",
  toggleFailed: "Could not save this setting",
  editRule: "Add or edit a rule",
  game: "Game",
  selectGame: "Select a game",
  gameListUnavailable: "Game list unavailable. Launch a game to select it here.",
  logFile: "Log file",
  selectLog: "Choose log file",
  marker: "Trigger text",
  saveFailed: "Could not save the rule. Choose a valid log file and enter a single line of trigger text.",
  saveRule: "Save rule",
  deleteFailed: "Could not delete the rule",
  deleteRule: "Delete rule",
  back: "Back",
  focus: {
    success: "Focus returned to the game",
    not_foreground: "Return to the running game, then open the plugin again",
    unavailable: "Focus switching is unavailable in this Gamescope session",
    unconfirmed: "Gamescope did not confirm the focus cycle",
    cancelled: "Focus cycle cancelled",
  },
};

export type Text = typeof zh;

export function getText(steamLocale?: string, systemLocale?: string): Text {
  const locale = (steamLocale?.trim() || systemLocale?.trim() || "").toLowerCase();
  return /^(?:zh(?:$|[-_])|schinese$|tchinese$)/.test(locale) ? zh : en;
}
