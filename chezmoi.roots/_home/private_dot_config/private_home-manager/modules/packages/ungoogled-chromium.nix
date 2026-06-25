{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.ungoogled-chromium;

  chromium = pkgs.ungoogled-chromium;
  # Chromium lowercases profile directory names; display name stays Slack@VASTSupport.
  profileDir = "slack@vastsupport";
  profileName = "Slack@VASTSupport";
  slackUrl = "https://app.slack.com/client/";
  vastSupportIcon =
    "${config.home.homeDirectory}/.local/share/chezmoi/docs/resources/icons/VASTSupport.png";

  chromiumConfigDir = "${config.home.homeDirectory}/.config/chromium";
  chromiumIconSrc = "${chromium}/share/icons/hicolor/256x256/apps/chromium.png";
  chromiumIconLocal = "${config.home.homeDirectory}/.local/share/pixmaps/chromium.png";

  chromium-bin-only = pkgs.buildEnv {
    name = "ungoogled-chromium-bin-only";
    paths = [ chromium ];
    pathsToLink = [ "/bin" ];
  };

  chromium-share = pkgs.buildEnv {
    name = "ungoogled-chromium-share";
    paths = [ chromium ];
    pathsToLink = [
      "/share/pixmaps"
      "/share/icons"
    ];
  };

  ungoogled-chromium-bin = pkgs.writeShellScriptBin "ungoogled-chromium" ''
    exec ${chromium-bin-only}/bin/chromium --profile-picker "$@"
  '';

  ungoogled-chromium-desktop = pkgs.makeDesktopItem {
    name = "ungoogled-chromium";
    desktopName = "Ungoogled Chromium";
    genericName = "Web Browser";
    comment = "Access the Internet (profile picker)";
    exec = "${ungoogled-chromium-bin}/bin/ungoogled-chromium %U";
    tryExec = "${ungoogled-chromium-bin}/bin/ungoogled-chromium";
    icon = chromiumIconLocal;
    categories = [ "Network" "WebBrowser" ];
    mimeTypes = [
      "application/pdf"
      "application/rdf+xml"
      "application/rss+xml"
      "application/xhtml+xml"
      "application/xhtml_xml"
      "application/xml"
      "image/gif"
      "image/jpeg"
      "image/png"
      "image/webp"
      "text/html"
      "text/xml"
      "x-scheme-handler/http"
      "x-scheme-handler/https"
    ];
    terminal = false;
    startupNotify = true;
    startupWMClass = "chromium-browser";
  };

  initSlackProfileScript = pkgs.writeShellScript "ungoogled-chromium-init-slack-vast-support-profile" ''
    set -euo pipefail

    config_dir="${chromiumConfigDir}"
    profile_dir="${profileDir}"
    profile_name="${profileName}"
    local_state="$config_dir/Local State"
    profile_path="$config_dir/$profile_dir"
    stale_profile_path="$config_dir/$stale_profile_dir"

    if [ -d "$stale_profile_path" ] && [ ! -d "$profile_path" ]; then
      mv "$stale_profile_path" "$profile_path"
    fi

    mkdir -p "$profile_path"

    prefs="$profile_path/Preferences"
    if [ ! -f "$prefs" ]; then
      ${pkgs.jq}/bin/jq -n --arg name "$profile_name" '{
        profile: { name: $name },
        signin: { allowed: false }
      }' > "$prefs"
    else
      tmp=$(mktemp)
      ${pkgs.jq}/bin/jq --arg name "$profile_name" '
        .profile //= {} |
        .profile.name = $name
      ' "$prefs" > "$tmp"
      mv "$tmp" "$prefs"
    fi

    profile_entry=$(${pkgs.jq}/bin/jq -n --arg name "$profile_name" '{
      active_time: (now | floor),
      name: $name,
      user_name: $name,
      is_using_default_name: false
    }')

    if [ ! -f "$local_state" ]; then
      ${pkgs.jq}/bin/jq -n --arg dir "$profile_dir" --argjson entry "$profile_entry" '{
        profile: {
          info_cache: { ($dir): $entry },
          profiles_order: [$dir]
        }
      }' > "$local_state"
    else
      tmp=$(mktemp)
      ${pkgs.jq}/bin/jq --arg dir "$profile_dir" --arg stale "$stale_profile_dir" --argjson entry "$profile_entry" '
        .profile //= {} |
        .profile.info_cache //= {} |
        .profile.info_cache[$dir] = (
          (.profile.info_cache[$dir] // {}) * $entry |
          .name = $entry.name |
          .user_name = $entry.user_name |
          .is_using_default_name = false
        ) |
        .profile.profiles_order = (
          (.profile.profiles_order // [] | map(select(. != $stale))) as $order |
          if ($order | index($dir)) then $order else $order + [$dir] end
        ) |
        del(.profile.info_cache[$stale])
      ' "$local_state" > "$tmp"
      mv "$tmp" "$local_state"
    fi
  '';

  slack-pwa-vast-support-launcher = pkgs.writeShellScriptBin "slack-vast-support-pwa" ''
    exec ${chromium-bin-only}/bin/chromium --profile-directory='${profileDir}' --app='${slackUrl}' "$@"
  '';

  slack-pwa-vast-support = pkgs.makeDesktopItem {
    name = "slack-vast-support-pwa";
    desktopName = "Slack@VASTSupport";
    genericName = "Chat";
    comment = "Slack web app for VAST Support on Slack@VASTSupport profile";
    exec = "${slack-pwa-vast-support-launcher}/bin/slack-vast-support-pwa";
    tryExec = "${slack-pwa-vast-support-launcher}/bin/slack-vast-support-pwa";
    icon = vastSupportIcon;
    categories = [ "Network" "Chat" ];
    terminal = false;
    startupNotify = true;
    startupWMClass = "chrome-app.slack.com__client-Default";
  };

  desktopCleanupAfter =
    if config.sz.platform.fedoraDesktop.enable then
      [ "syncNixDesktopEntries" ]
    else
      [ "installPackages" ];

  desktopCleanupScript = pkgs.writeShellScript "ungoogled-chromium-desktop-cleanup" ''
    appdir="$HOME/.local/share/applications"
    rm -f "$appdir/chromium-browser.desktop"
    rm -f "$appdir/chromium.desktop"
    rm -f "$appdir/slack-vastsupport-pwa.desktop"
    if [ -d "$appdir" ] && command -v update-desktop-database >/dev/null; then
      update-desktop-database "$appdir" 2>/dev/null || true
    fi
  '';

  iconInstallScript = pkgs.writeShellScript "ungoogled-chromium-icon-install" ''
    pixmapdir="$HOME/.local/share/pixmaps"
    icondir="$HOME/.local/share/icons"
    mkdir -p "$pixmapdir" "$icondir/hicolor/256x256/apps"
    cp -Lf "${chromiumIconSrc}" "$pixmapdir/chromium.png"
    chmod a+r "$pixmapdir/chromium.png"
    for size in 16x16 24x24 48x48 64x64 128x128 256x256; do
      src="${chromium}/share/icons/hicolor/$size/apps/chromium.png"
      if [ -f "$src" ]; then
        mkdir -p "$icondir/hicolor/$size/apps"
        cp -Lf "$src" "$icondir/hicolor/$size/apps/chromium.png"
        chmod a+r "$icondir/hicolor/$size/apps/chromium.png"
      fi
    done
    if [ -d "$icondir/hicolor" ] && command -v gtk-update-icon-cache >/dev/null; then
      chmod -R u+w "$icondir" 2>/dev/null || true
      gtk-update-icon-cache -f -t "$icondir/hicolor" 2>/dev/null || true
    fi
  '';

  patchDesktopScript = pkgs.writeShellScript "ungoogled-chromium-patch-desktop" ''
    desktop="$HOME/.local/share/applications/ungoogled-chromium.desktop"
    icon="${chromiumIconLocal}"
    if [ -f "$desktop" ]; then
      ${pkgs.gnused}/bin/sed -i "s|^Icon=.*|Icon=$icon|" "$desktop"
    fi
  '';
in
{
  options.sz.packages.ungoogled-chromium = {
    enable = lib.mkEnableOption "Ungoogled Chromium";

    slackPwaVastSupport.enable = lib.mkEnableOption "Slack PWA for VAST Support on Slack@VASTSupport profile";
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      chromium-bin-only
      chromium-share
      ungoogled-chromium-bin
      ungoogled-chromium-desktop
    ]
    ++ lib.optionals cfg.slackPwaVastSupport.enable [
      slack-pwa-vast-support-launcher
      slack-pwa-vast-support
    ];

    home.activation.ungoogledChromiumIconInstall = lib.hm.dag.entryAfter [ "installPackages" ] ''
      $DRY_RUN_CMD ${iconInstallScript}
    '';

    home.activation.ungoogledChromiumDesktopCleanup = lib.hm.dag.entryAfter desktopCleanupAfter ''
      $DRY_RUN_CMD ${desktopCleanupScript}
    '';

    home.activation.ungoogledChromiumPatchDesktop = lib.hm.dag.entryAfter [ "ungoogledChromiumDesktopCleanup" ] ''
      $DRY_RUN_CMD ${patchDesktopScript}
    '';

    home.activation.ungoogledChromiumSlackVastSupportProfile = lib.mkIf cfg.slackPwaVastSupport.enable (
      lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        $DRY_RUN_CMD ${initSlackProfileScript}
      ''
    );
  };
}
