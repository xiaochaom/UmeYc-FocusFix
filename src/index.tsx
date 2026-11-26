import { callable, definePlugin, FileSelectionType, openFilePicker, toaster } from "@decky/api";
import { ButtonItem, DropdownItem, PanelSection, Router, TextField, ToggleField } from "@decky/ui";
import { useEffect, useState } from "react";
import { FaCrosshairs } from "react-icons/fa";

type Game = { id: string; name: string };
type Config = { name: string; log_path: string; marker: string; enabled: boolean };
type Configs = Record<string, Config>;
type Settings = { enabled: boolean; configs: Configs; home: string };
type App = { appid: number | string; display_name: string; app_type?: number };
type Collection = { allApps?: Iterable<App> };
type LibraryWindow = Window & {
  collectionStore?: {
    allGamesCollection?: Collection;
    localGamesCollection?: Collection;
    deckDesktopApps?: Collection;
  };
};
type FocusResult = "success" | "not_foreground" | "unavailable" | "unconfirmed" | "cancelled";

const getSettings = callable<[], Settings>("get_settings");
const setStarRail = callable<[boolean], { enabled: boolean }>("set_star_rail");
const focusGame = callable<[string], FocusResult>("focus_current_game");
const saveConfig = callable<[string, string, string, string], Configs>("save_game_config");
const toggleConfig = callable<[string, boolean], Configs>("set_game_config");
const deleteConfig = callable<[string], Configs>("delete_game_config");
const messages: Record<FocusResult, string> = {
  success: "已切换焦点并返回游戏",
  not_foreground: "请先返回运行中的游戏，再打开插件操作",
  unavailable: "当前 Gamescope 会话无法切换焦点",
  unconfirmed: "Gamescope 未确认焦点已完成切换",
  cancelled: "焦点切换已取消",
};

function listGames(): Game[] {
  const collections = (window as LibraryWindow).collectionStore;
  const games = new Map<string, Game>();
  for (const collection of [
    collections?.allGamesCollection, collections?.localGamesCollection, collections?.deckDesktopApps,
  ]) {
    for (const app of collection?.allApps ?? []) {
      if (app.app_type !== 1 && app.app_type !== 1073741824) continue;
      const id = String(Number(app.appid) >>> 0);
      if (id !== "0" && app.display_name) games.set(id, { id, name: app.display_name });
    }
  }
  for (const app of Router.RunningApps ?? []) {
    const id = String(Number(app.appid) >>> 0);
    if (id !== "0" && app.display_name) games.set(id, { id, name: app.display_name });
  }
  return Array.from(games.values()).sort((a, b) => a.name.localeCompare(b.name));
}

function CustomRules({ settings }: { settings: Settings }) {
  const [configs, setConfigs] = useState(settings.configs);
  const [editing, setEditing] = useState(false);
  const [games, setGames] = useState<Game[]>([]);
  const [selected, setSelected] = useState<Game>();
  const [path, setPath] = useState("");
  const [marker, setMarker] = useState("");
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState("");

  function edit(game?: Game) {
    const available = listGames();
    if (game && !available.some((entry) => entry.id === game.id)) available.unshift(game);
    setGames(available);
    setSelected(game);
    setPath(game ? configs[game.id]?.log_path ?? "" : "");
    setMarker(game ? configs[game.id]?.marker ?? "" : "");
    setError("");
    setEditing(true);
  }

  function select(game: Game) {
    setSelected(game);
    setPath(configs[game.id]?.log_path ?? "");
    setMarker(configs[game.id]?.marker ?? "");
    setError("");
  }

  async function chooseLog() {
    setPicking(true);
    try {
      const parent = path.slice(0, path.lastIndexOf("/"));
      const chosen = await openFilePicker(
        FileSelectionType.FILE, parent || settings.home,
        true, true, undefined, ["log", "txt"], true,
      );
      setPath(chosen.realpath || chosen.path);
      setError("");
    } catch {
      // The picker rejects when it is closed without a selection.
    } finally {
      setPicking(false);
    }
  }

  async function update(action: () => Promise<Configs>, failure: string, close = false) {
    setBusy(true);
    setError("");
    try {
      setConfigs(await action());
      if (close) setEditing(false);
    } catch {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const locked = busy || picking;
  return (
    <PanelSection title="自定义自动修复">
      {Object.entries(configs).map(([id, config]) => (
        <ToggleField
          key={id}
          label={config.name}
          checked={config.enabled}
          disabled={locked || editing}
          onChange={(value) => void update(() => toggleConfig(id, value), "无法保存开关")}
        />
      ))}
      {!editing && (
        <ButtonItem layout="below" onClick={() => edit()} disabled={locked}>
          添加或编辑规则
        </ButtonItem>
      )}
      {editing && (
        <>
          <DropdownItem
            label="游戏"
            strDefaultLabel="选择游戏"
            rgOptions={games.map((game) => ({ data: game.id, label: game.name }))}
            selectedOption={selected?.id}
            disabled={locked}
            onChange={({ data }) => {
              const game = games.find((entry) => entry.id === data);
              if (game) select(game);
            }}
          />
          {games.length === 0 && <div role="status">游戏列表不可用。启动游戏后可在这里选择。</div>}
          <ButtonItem
            layout="below"
            label="日志文件"
            description={path ? <span style={{ overflowWrap: "anywhere" }}>{path}</span> : undefined}
            disabled={!selected || locked}
            onClick={chooseLog}
          >
            选择日志文件
          </ButtonItem>
          <TextField
            label="触发行"
            value={marker}
            disabled={!selected || locked}
            onChange={(event) => setMarker(event.target.value)}
          />
          <ButtonItem
            layout="below"
            disabled={!selected || !path || !marker.trim() || locked}
            onClick={() => {
              if (selected) void update(
                () => saveConfig(selected.id, selected.name, path, marker),
                "无法保存。请选择有效的日志文件，并填写一行触发文字。", true,
              );
            }}
          >
            保存规则
          </ButtonItem>
          {selected && configs[selected.id] && (
            <ButtonItem
              layout="below"
              disabled={locked}
              onClick={() => void update(() => deleteConfig(selected.id), "无法删除规则", true)}
            >
              删除规则
            </ButtonItem>
          )}
          <ButtonItem layout="below" disabled={locked} onClick={() => setEditing(false)}>
            返回
          </ButtonItem>
        </>
      )}
      {error && <div role="status">{error}</div>}
    </PanelSection>
  );
}

function FocusFix() {
  const [settings, setSettings] = useState<Settings>();
  const [saving, setSaving] = useState(false);
  const [focusing, setFocusing] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [runningApp, setRunningApp] = useState(() => Router.MainRunningApp?.appid);

  useEffect(() => {
    let active = true;
    getSettings().then(
      (value) => { if (active) setSettings(value); },
      () => { if (active) setLoadFailed(true); },
    );
    const timer = window.setInterval(() => setRunningApp(Router.MainRunningApp?.appid), 400);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function toggle(value: boolean) {
    setSaving(true);
    try {
      const result = await setStarRail(value);
      setSettings((previous) => previous && { ...previous, enabled: result.enabled });
    } catch {
      toaster.toast({ title: "UmeYc-FocusFix", body: "无法保存自动修复设置" });
    } finally {
      setSaving(false);
    }
  }

  async function focus() {
    const app = Router.MainRunningApp?.appid;
    if (!app) return;
    setFocusing(true);
    try {
      Router.CloseSideMenus();
      const result = await focusGame(String(app));
      toaster.toast({ title: "UmeYc-FocusFix", body: messages[result] });
    } catch {
      toaster.toast({ title: "UmeYc-FocusFix", body: "无法切换当前游戏的焦点" });
    } finally {
      setFocusing(false);
    }
  }

  return (
    <>
      <PanelSection>
        <ToggleField
          label="崩坏：星穹铁道"
          description={loadFailed ? "无法读取设置" : "自动修复"}
          checked={settings?.enabled ?? false}
          disabled={!settings || saving}
          onChange={toggle}
        />
        <ButtonItem layout="below" disabled={!runningApp || focusing} onClick={focus}>
          手动切换焦点
        </ButtonItem>
      </PanelSection>
      {settings && <CustomRules settings={settings} />}
    </>
  );
}

export default definePlugin(() => ({
  name: "UmeYc-FocusFix",
  titleView: <div>UmeYc-FocusFix</div>,
  content: <FocusFix />,
  icon: <FaCrosshairs />,
  alwaysRender: true,
}));
