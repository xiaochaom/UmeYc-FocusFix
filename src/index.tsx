import { callable, definePlugin, FileSelectionType, openFilePicker, toaster } from "@decky/api";
import { ButtonItem, DropdownItem, PanelSection, Router, TextField, ToggleField } from "@decky/ui";
import { useEffect, useState } from "react";
import { FaCrosshairs } from "react-icons/fa";
import { getText, type Text } from "./i18n";

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
type FocusResult = keyof Text["focus"];

const getSettings = callable<[], Settings>("get_settings");
const setStarRail = callable<[boolean], { enabled: boolean }>("set_star_rail");
const focusGame = callable<[string], FocusResult>("focus_current_game");
const saveConfig = callable<[string, string, string, string], Configs>("save_game_config");
const toggleConfig = callable<[string, boolean], Configs>("set_game_config");
const deleteConfig = callable<[string], Configs>("delete_game_config");

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

type RuleError = "toggleFailed" | "saveFailed" | "deleteFailed";

function CustomRules({ settings, text }: { settings: Settings; text: Text }) {
  const [configs, setConfigs] = useState(settings.configs);
  const [editing, setEditing] = useState(false);
  const [games, setGames] = useState<Game[]>([]);
  const [selected, setSelected] = useState<Game>();
  const [path, setPath] = useState("");
  const [marker, setMarker] = useState("");
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<RuleError>();

  function edit(game?: Game) {
    const available = listGames();
    if (game && !available.some((entry) => entry.id === game.id)) available.unshift(game);
    setGames(available);
    setSelected(game);
    setPath(game ? configs[game.id]?.log_path ?? "" : "");
    setMarker(game ? configs[game.id]?.marker ?? "" : "");
    setError(undefined);
    setEditing(true);
  }

  function select(game: Game) {
    setSelected(game);
    setPath(configs[game.id]?.log_path ?? "");
    setMarker(configs[game.id]?.marker ?? "");
    setError(undefined);
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
      setError(undefined);
    } catch {
      // The picker rejects when it is closed without a selection.
    } finally {
      setPicking(false);
    }
  }

  async function update(action: () => Promise<Configs>, failure: RuleError, close = false) {
    setBusy(true);
    setError(undefined);
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
    <PanelSection title={text.customRules}>
      {Object.entries(configs).map(([id, config]) => (
        <ToggleField
          key={id}
          label={config.name}
          checked={config.enabled}
          disabled={locked || editing}
          onChange={(value) => void update(() => toggleConfig(id, value), "toggleFailed")}
        />
      ))}
      {!editing && (
        <ButtonItem layout="below" onClick={() => edit()} disabled={locked}>
          {text.editRule}
        </ButtonItem>
      )}
      {editing && (
        <>
          <DropdownItem
            label={text.game}
            strDefaultLabel={text.selectGame}
            rgOptions={games.map((game) => ({ data: game.id, label: game.name }))}
            selectedOption={selected?.id}
            disabled={locked}
            onChange={({ data }) => {
              const game = games.find((entry) => entry.id === data);
              if (game) select(game);
            }}
          />
          {games.length === 0 && <div role="status">{text.gameListUnavailable}</div>}
          <ButtonItem
            layout="below"
            label={text.logFile}
            description={path ? <span style={{ overflowWrap: "anywhere" }}>{path}</span> : undefined}
            disabled={!selected || locked}
            onClick={chooseLog}
          >
            {text.selectLog}
          </ButtonItem>
          <TextField
            label={text.marker}
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
                "saveFailed", true,
              );
            }}
          >
            {text.saveRule}
          </ButtonItem>
          {selected && configs[selected.id] && (
            <ButtonItem
              layout="below"
              disabled={locked}
              onClick={() => void update(() => deleteConfig(selected.id), "deleteFailed", true)}
            >
              {text.deleteRule}
            </ButtonItem>
          )}
          <ButtonItem layout="below" disabled={locked} onClick={() => setEditing(false)}>
            {text.back}
          </ButtonItem>
        </>
      )}
      {error && <div role="status">{text[error]}</div>}
    </PanelSection>
  );
}

function FocusFix() {
  const text = getText(window.LocalizationManager?.m_rgLocalesToUse?.[0], window.navigator.language);
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
      toaster.toast({ title: "UmeYc-FocusFix", body: text.autoSaveFailed });
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
      toaster.toast({ title: "UmeYc-FocusFix", body: text.focus[result] });
    } catch {
      toaster.toast({ title: "UmeYc-FocusFix", body: text.manualFailed });
    } finally {
      setFocusing(false);
    }
  }

  return (
    <>
      <PanelSection>
        <ToggleField
          label={text.starRail}
          description={loadFailed ? text.loadFailed : text.automatic}
          checked={settings?.enabled ?? false}
          disabled={!settings || saving}
          onChange={toggle}
        />
        <ButtonItem layout="below" disabled={!runningApp || focusing} onClick={focus}>
          {text.manual}
        </ButtonItem>
      </PanelSection>
      {settings && <CustomRules settings={settings} text={text} />}
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
