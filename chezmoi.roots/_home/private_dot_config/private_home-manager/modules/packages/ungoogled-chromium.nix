{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.ungoogled-chromium;

  chromium = pkgs.ungoogled-chromium;
  profileDir = "Slack@vastsupport";
  profileName = "Slack@vastsupport";
  slackUrl = "https://app.slack.com/client/";

  chromiumConfigDir = "${config.home.homeDirectory}/.config/chromium";

  initSlackProfileScript = pkgs.writeShellScript "ungoogled-chromium-init-slack-profile" ''
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

  slack-pwa-launcher = pkgs.writeShellScriptBin "slack-vastsupport-pwa" ''
    exec ${chromium}/bin/chromium --profile-directory='${profileDir}' --app='${slackUrl}' "$@"
  '';

  slack-pwa = pkgs.makeDesktopItem {
    name = "slack-vastsupport-pwa";
    desktopName = "Slack (PWA)";
    genericName = "Chat (PWA)";
    comment = "Slack web app on Slack@vastsupport profile";
    exec = "${slack-pwa-launcher}/bin/slack-vastsupport-pwa";
    tryExec = "${slack-pwa-launcher}/bin/slack-vastsupport-pwa";
    icon = "slack";
    categories = [ "Network" "Chat" ];
    terminal = false;
    startupNotify = true;
    startupWMClass = "chrome-app.slack.com__client-Default";
  };
in
{
  options.sz.packages.ungoogled-chromium = {
    enable = lib.mkEnableOption "Ungoogled Chromium";

    slackPwa.enable = lib.mkEnableOption "Slack PWA on Slack@vastsupport profile";
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ chromium ]
      ++ lib.optionals cfg.slackPwa.enable [
        slack-pwa-launcher
        slack-pwa
      ];

    home.activation.ungoogledChromiumSlackProfile = lib.mkIf cfg.slackPwa.enable (
      lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        $DRY_RUN_CMD ${initSlackProfileScript}
      ''
    );
  };
}
