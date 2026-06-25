{ config, pkgs, lib, ... }:

let
  cfg = config.services.gearlever;

  gearlever = pkgs.writeShellScriptBin "gearlever" ''
    export GSK_RENDERER=cairo
    exec ${pkgs.gearlever}/bin/gearlever "$@"
  '';

  beeperUpdateUrl =
    "https://api.beeper.com/desktop/download/linux/x64/stable/com.automattic.beeper.desktop";

  beeperInstallScript = pkgs.writeShellScript "gearlever-beeper-install" ''
    set -euo pipefail

    gearlever="${gearlever}/bin/gearlever"
    curl=${pkgs.curl}/bin/curl
    appimages="${cfg.appImagesDir}"
    beeper="$appimages/${cfg.apps.beeper.fileName}"
    update_url="${cfg.apps.beeper.updateUrl}"

    mkdir -p "$appimages"

    if [ ! -f "$beeper" ]; then
      tmp="$beeper.partial"
      "$curl" -fL "$update_url" -o "$tmp"
      chmod +x "$tmp"
      mv "$tmp" "$beeper"
    fi

    if ! "$gearlever" --list-installed 2>/dev/null | grep -Fq "$beeper"; then
      "$gearlever" --integrate -y --replace "$beeper"
    fi

    "$gearlever" --set-update-url "$beeper" --url "$update_url"
  '';

  beeperDesktop = pkgs.makeDesktopItem {
    name = "beeper";
    desktopName = "Beeper";
    genericName = "Chat";
    comment = "Universal chat app";
    exec = "${cfg.appImagesDir}/${cfg.apps.beeper.fileName}";
    tryExec = "${cfg.appImagesDir}/${cfg.apps.beeper.fileName}";
    icon = "beepertexts";
    categories = [ "Network" "Chat" ];
    terminal = false;
    startupNotify = true;
  };

  beeperIconScript = pkgs.writeShellScript "gearlever-beeper-icon" ''
    set -euo pipefail
    beeper="${cfg.appImagesDir}/${cfg.apps.beeper.fileName}"
    icondir="$HOME/.local/share/icons/hicolor/512x512/apps"
    icon="$icondir/beepertexts.png"
    [ -f "$beeper" ] || exit 0
    [ -f "$icon" ] && exit 0
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    cd "$tmp"
    "$beeper" --appimage-extract usr/share/icons/hicolor/512x512/apps/beepertexts.png >/dev/null 2>&1
    mkdir -p "$icondir"
    chmod -R u+w "$HOME/.local/share/icons" 2>/dev/null || true
    rm -f "$icon"
    cp squashfs-root/usr/share/icons/hicolor/512x512/apps/beepertexts.png "$icon"
    chmod a+r "$icon"
    if command -v gtk-update-icon-cache >/dev/null; then
      gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi
  '';

  beeperUpdateScript = pkgs.writeShellScript "gearlever-beeper-update" ''
    set -euo pipefail

    gearlever="${gearlever}/bin/gearlever"
    appimages="${cfg.appImagesDir}"
    beeper="$appimages/${cfg.apps.beeper.fileName}"
    update_url="${cfg.apps.beeper.updateUrl}"

    [ -f "$beeper" ] || exit 0

    "$gearlever" --set-update-url "$beeper" --url "$update_url"

    if "$gearlever" --list-updates 2>/dev/null | grep -Fq "$beeper"; then
      "$gearlever" --update -y "$beeper"
    fi
  '';
in
{
  options.services.gearlever = {
    enable = lib.mkEnableOption "Gear Lever AppImage management";

    appImagesDir = lib.mkOption {
      type = lib.types.str;
      default = "${config.home.homeDirectory}/AppImages";
      description = "Directory where Gear Lever stores integrated AppImages.";
    };

    apps.beeper = {
      enable = lib.mkEnableOption "Manage Beeper as a Gear Lever AppImage";

      fileName = lib.mkOption {
        type = lib.types.str;
        default = "beeper.appimage";
      };

      updateUrl = lib.mkOption {
        type = lib.types.str;
        default = beeperUpdateUrl;
        description = "Stable Beeper Linux x64 redirect URL used for install and updates.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      (lib.lowPrio pkgs.gearlever)
      gearlever
    ]
    ++ lib.optional cfg.apps.beeper.enable beeperDesktop;

    home.activation.gearleverApps = lib.mkIf cfg.apps.beeper.enable (lib.hm.dag.entryAfter [ "syncNixDesktopEntries" ] ''
      $DRY_RUN_CMD ${beeperInstallScript}
      $DRY_RUN_CMD ${beeperIconScript}
    '');

    systemd.user.services.gearlever-beeper-update = lib.mkIf cfg.apps.beeper.enable {
      Unit = {
        Description = "Update Beeper AppImage via Gear Lever";
      };
      Service = {
        Type = "oneshot";
        ExecStart = beeperUpdateScript;
      };
    };

    systemd.user.timers.gearlever-beeper-update = lib.mkIf cfg.apps.beeper.enable {
      Unit = {
        Description = "Weekly Beeper AppImage update check";
      };
      Timer = {
        OnCalendar = "weekly";
        Persistent = true;
      };
      Install = {
        WantedBy = [ "timers.target" ];
      };
    };
  };
}
