{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.ungoogled-chromium;

  chromium = pkgs.ungoogled-chromium;
  profileDir = "Slack@VASTSupport";
  profileName = "Slack@VASTSupport";
  slackUrl = "https://app.slack.com/client/";
  vastSupportIcon =
    "${config.home.homeDirectory}/.local/share/chezmoi/docs/resources/icons/VASTSupport.png";

  chromiumConfigDir = "${config.home.homeDirectory}/.config/chromium";

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
      ${pkgs.jq}/bin/jq --arg dir "$profile_dir" --argjson entry "$profile_entry" '
        .profile //= {} |
        .profile.info_cache //= {} |
        .profile.info_cache[$dir] = (.profile.info_cache[$dir] // $entry) |
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

  slack-pwa-vast-support-launcher = pkgs.writeShellScriptBin "slack-vast-support-pwa" ''
    exec ${chromium}/bin/chromium --profile-directory='${profileDir}' --app='${slackUrl}' "$@"
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
in
{
  options.sz.packages.ungoogled-chromium = {
    enable = lib.mkEnableOption "Ungoogled Chromium";

    slackPwaVastSupport.enable = lib.mkEnableOption "Slack PWA for VAST Support on Slack@VASTSupport profile";
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ chromium ]
      ++ lib.optionals cfg.slackPwaVastSupport.enable [
        slack-pwa-vast-support-launcher
        slack-pwa-vast-support
      ];

    home.activation.ungoogledChromiumSlackVastSupportProfile = lib.mkIf cfg.slackPwaVastSupport.enable (
      lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        $DRY_RUN_CMD ${initSlackProfileScript}
      ''
    );
  };
}
