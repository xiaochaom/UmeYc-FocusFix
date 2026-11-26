# UmeYc-FocusFix

[简体中文](README.md)

A Decky plugin for Steam Deck games where controller or relative mouse input stops responding until the game loses and regains focus.

## Usage

1. Enable Developer Mode in Decky settings. Choose **Install Plugin from ZIP File** and select `UmeYc-FocusFix.zip`.
2. **Honkai: Star Rail** has an automatic fix toggle, which is off by default. When enabled, the plugin finds the running game's Wine or Proton prefix and watches the current Unity log for the scene-loading marker. It attempts one focus cycle per launch.
3. **Manual focus cycle** closes the Quick Access Menu and tries to move focus away from the current game and back. The button is disabled when no game is running. It works with automatic fixes turned off.
4. To add a custom rule, choose a game or non-Steam shortcut, pick its `.log` or `.txt` file, and enter a stable substring from the trigger line. Matching uses the literal UTF-8 text. Each game's rule can be toggled, edited, or removed.

Games start through Steam as usual. The plugin uses Gamescope to switch focus in Gaming Mode. The Star Rail preset detects its Wine prefix automatically. Custom rules only require a game, a log file, and a trigger string. Restart the game after saving a rule to test when it triggers.

This version targets SteamOS Gaming Mode. The running process must expose the game's Steam AppID for automatic fixes. Custom log files can live under your home directory, `/run/media/<user>`, or `/mnt`. Third-party launchers such as THRL Flatpak and in-game input recovery still need verification on a Steam Deck.

## Build

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm check
python3 -m unittest discover -s tests
pnpm package
```

The installable ZIP is at `out/UmeYc-FocusFix.zip`.

## Acknowledgments

- **zhh7ce** shared the focus-bridge approach and the Honkai: Star Rail scene marker. This plugin uses the same trigger and implements the focus cycle through Gamescope. [Focus-bridge Gist](https://gist.github.com/zhh7ce/a075e591cab7c3bd9066eb51d99b5892) · [Star Rail configuration](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-2088)
- **NEORUAA** documented input recovery after a focus cycle. **ericcccc21** shared the manual Game Tools workaround. **xiaochaom** reported the issue and tested both the workaround and the Gist's focus bridge. [Issue](https://dawn.wine/dawn-winery/dwproton/issues/44) · [Focus investigation](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-1862) · [Manual workaround](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-2033) · [Focus bridge verification](https://dawn.wine/dawn-winery/dwproton/issues/44#issuecomment-2089)
- Thanks to the **Decky Loader** and **Valve Gamescope** developers. [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) · [Gamescope](https://github.com/ValveSoftware/gamescope)
