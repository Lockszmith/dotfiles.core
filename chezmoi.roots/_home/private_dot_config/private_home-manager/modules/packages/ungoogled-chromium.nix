{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.ungoogled-chromium;

  chromium = pkgs.ungoogled-chromium;
  # Chromium lowercases profile directory names with _. prefix; display name: Slack@VASTSupport.
  profileDir = "_.slack@vastsupport";
  profileName = "Slack@VASTSupport";
  slackUrl = "https://app.slack.com/client/";
  iconBase = "${config.home.homeDirectory}/.local/share/icons/hicolor/256x256/apps";
  pixmapBase = "${config.home.homeDirectory}/.local/share/pixmaps";
  vastSupportIconLocal = "${iconBase}/slack-vast-support.png";
  ungoogledIconLocal = "${pixmapBase}/ungoogled-chromium.png";
  ungoogledIconSrc =
    "${config.home.homeDirectory}/.local/share/chezmoi/docs/resources/icons/ungoogled-chromium-p.png";
  vastSupportIconSrc =
    "${config.home.homeDirectory}/.local/share/chezmoi/docs/resources/icons/VASTSupport.png";

  chromiumConfigDir = "${config.home.homeDirectory}/.config/chromium";

  chromium-bin-only = pkgs.buildEnv {
    name = "ungoogled-chromium-bin-only";
    paths = [ chromium ];
    pathsToLink = [ "/bin" ];
  };

  ungoogled-chromium-bin = pkgs.writeShellScriptBin "ungoogled-chromium" ''
    exec ${chromium-bin-only}/bin/chromium "$@"
  '';

  ungoogled-chromium-desktop = pkgs.makeDesktopItem {
    name = "ungoogled-chromium";
    desktopName = "Ungoogled Chromium";
    genericName = "Web Browser";
    comment = "Access the Internet (profile picker)";
    exec = "${ungoogled-chromium-bin}/bin/ungoogled-chromium %U";
    tryExec = "${ungoogled-chromium-bin}/bin/ungoogled-chromium";
    icon = ungoogledIconLocal;
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

  initProfilePickerScript = pkgs.writeShellScript "ungoogled-chromium-init-profile-picker" ''
    set -euo pipefail

    config_dir="${chromiumConfigDir}"
    local_state="$config_dir/Local State"
    mkdir -p "$config_dir"

    if [ ! -f "$local_state" ]; then
      ${pkgs.jq}/bin/jq -n '{
        profile: { picker_availability_on_startup: 2 }
      }' > "$local_state"
    else
      tmp=$(mktemp)
      ${pkgs.jq}/bin/jq '
        .profile //= {} |
        .profile.picker_availability_on_startup = 2
      ' "$local_state" > "$tmp"
      mv "$tmp" "$local_state"
    fi
  '';

  initSlackProfileScript = pkgs.writeShellScript "ungoogled-chromium-init-slack-vast-support-profile" ''
    set -euo pipefail

    config_dir="${chromiumConfigDir}"
    profile_dir="${profileDir}"
    profile_name="${profileName}"
    local_state="$config_dir/Local State"
    profile_path="$config_dir/$profile_dir"

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
          picker_availability_on_startup: 2,
          info_cache: { ($dir): $entry },
          profiles_order: [$dir]
        }
      }' > "$local_state"
    else
      tmp=$(mktemp)
      ${pkgs.jq}/bin/jq --arg dir "$profile_dir" --argjson entry "$profile_entry" '
        .profile //= {} |
        .profile.picker_availability_on_startup = 2 |
        .profile.info_cache //= {} |
        .profile.info_cache[$dir] = (
          (.profile.info_cache[$dir] // {}) * $entry |
          .name = $entry.name |
          .user_name = $entry.user_name |
          .is_using_default_name = false
        ) |
        .profile.profiles_order = (
          if (.profile.profiles_order // [] | index($dir)) then
            .profile.profiles_order
          else
            (.profile.profiles_order // []) + [$dir]
          end
        )
      ' "$local_state" > "$tmp"
      mv "$tmp" "$local_state"
    fi
  '';

  slackPwaWmClass = "chrome-app.slack.com__client_-_.slack@vastsupport";

  slack-pwa-vast-support-launcher = pkgs.writeShellScriptBin "slack-vast-support-pwa" ''
    exec ${chromium-bin-only}/bin/chromium \
      --profile-directory='${profileDir}' \
      --app='${slackUrl}' \
      "$@"
  '';

  slack-pwa-vast-support = pkgs.makeDesktopItem {
    name = "slack-vast-support";
    desktopName = "Slack@VASTSupport";
    genericName = "Chat";
    comment = "Slack web app for VAST Support on Slack@VASTSupport profile";
    exec = "${slack-pwa-vast-support-launcher}/bin/slack-vast-support-pwa";
    tryExec = "${slack-pwa-vast-support-launcher}/bin/slack-vast-support-pwa";
    icon = vastSupportIconLocal;
    categories = [ "Network" "Chat" ];
    terminal = false;
    startupNotify = true;
    startupWMClass = slackPwaWmClass;
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
    rm -f "$appdir/slack-vast-support-pwa.desktop"
    if [ -d "$appdir" ] && command -v update-desktop-database >/dev/null; then
      update-desktop-database "$appdir" 2>/dev/null || true
    fi
  '';

  iconInstallScript = pkgs.writeShellScript "ungoogled-chromium-icon-install" ''
    set -euo pipefail
    u_src="${ungoogledIconSrc}"
    s_src="${vastSupportIconSrc}"
    u_pixmap="${ungoogledIconLocal}"
    s_pixmap="${pixmapBase}/slack-vast-support.png"
    u_icon="${iconBase}/ungoogled-chromium.png"
    s_icon="${vastSupportIconLocal}"
    mkdir -p "$(dirname "$u_pixmap")" "$(dirname "$s_pixmap")" "$(dirname "$u_icon")"
    if [ ! -f "$u_src" ]; then
      echo "ungoogled-chromium icon missing at $u_src" >&2
      exit 1
    fi
    if [ ! -f "$s_src" ]; then
      echo "Slack PWA icon missing at $s_src" >&2
      exit 1
    fi
    for pair in "$u_src:$u_pixmap" "$u_src:$u_icon" "$s_src:$s_pixmap" "$s_src:$s_icon"; do
      src="''${pair%%:*}"
      dst="''${pair#*:}"
      cp -Lf "$src" "$dst"
      chmod a+r "$dst"
    done
    # GNOME launcher/Alt-Tab often need smaller hicolor sizes, not just 256x256.
    for size in 48 128 256; do
      dir="$HOME/.local/share/icons/hicolor/''${size}x''${size}/apps"
      mkdir -p "$dir"
      cp -Lf "$s_src" "$dir/slack-vast-support.png"
      chmod a+r "$dir/slack-vast-support.png"
    done
    if command -v gtk-update-icon-cache >/dev/null; then
      chmod -R u+w "$HOME/.local/share/icons" 2>/dev/null || true
      gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi
  '';

  patchDesktopScript = pkgs.writeShellScript "ungoogled-chromium-patch-desktop" ''
    appdir="$HOME/.local/share/applications"
    u_desktop="$appdir/ungoogled-chromium.desktop"
    s_desktop="$appdir/slack-vast-support.desktop"
    s_alias="$appdir/chrome-slack-vast-support-wmclass.desktop"
    u_icon="${ungoogledIconLocal}"
    s_icon="${vastSupportIconLocal}"
    s_wmclass="${slackPwaWmClass}"
    s_exec="${slack-pwa-vast-support-launcher}/bin/slack-vast-support-pwa"
    if [ -f "$u_desktop" ]; then
      ${pkgs.gnused}/bin/sed -i "s|^Icon=.*|Icon=$u_icon|" "$u_desktop"
    fi
    if [ -f "$s_desktop" ]; then
      ${pkgs.gnused}/bin/sed -i \
        -e "s|^Icon=.*|Icon=$s_icon|" \
        -e "s|^StartupWMClass=.*|StartupWMClass=$s_wmclass|" \
        "$s_desktop"
    fi
    # GNOME Alt-Tab matches WM_CLASS from Chromium --app windows; alias helps when
    # the shell fails to associate the visible launcher entry with the window class.
    cat > "$s_alias" <<EOF
[Desktop Entry]
Type=Application
Version=1.5
Name=Slack@VASTSupport
Comment=Slack web app WM class alias for GNOME window matching
Exec=$s_exec
TryExec=$s_exec
Icon=$s_icon
StartupNotify=true
StartupWMClass=$s_wmclass
Terminal=false
NoDisplay=true
EOF
    chmod a+r "$s_alias"
    if command -v update-desktop-database >/dev/null; then
      update-desktop-database "$appdir" 2>/dev/null || true
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

    home.activation.ungoogledChromiumProfilePicker = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD ${initProfilePickerScript}
    '';

    home.activation.ungoogledChromiumDesktopCleanup = lib.hm.dag.entryAfter desktopCleanupAfter ''
      $DRY_RUN_CMD ${desktopCleanupScript}
    '';

    home.activation.ungoogledChromiumPatchDesktop = lib.hm.dag.entryAfter [
      "ungoogledChromiumDesktopCleanup"
      "dedupDesktopEntries"
    ] ''
      $DRY_RUN_CMD ${patchDesktopScript}
    '';

    home.activation.ungoogledChromiumSlackVastSupportProfile = lib.mkIf cfg.slackPwaVastSupport.enable (
      lib.hm.dag.entryAfter [ "ungoogledChromiumProfilePicker" ] ''
        $DRY_RUN_CMD ${initSlackProfileScript}
      ''
    );
  };
}
