{ config, pkgs, lib, ... }:

let
  cfg = config.sz.autostart;

  gearleverCfg = config.services.gearlever;
  beeperExec = "${gearleverCfg.appImagesDir}/${gearleverCfg.apps.beeper.fileName}";

  autostartExtra = {
    "X-GNOME-Autostart-enabled" = "true";
    "X-GNOME-Autostart-Delay" = "3";
  };

  beeperAutostart = pkgs.makeDesktopItem {
    name = "beeper-autostart";
    desktopName = "Beeper";
    exec = beeperExec;
    terminal = false;
    extraConfig = autostartExtra;
  };

  slackPwaAutostart = pkgs.makeDesktopItem {
    name = "slack-pwa-vast-support-autostart";
    desktopName = "Slack@VASTSupport";
    exec = "${config.home.homeDirectory}/.nix-profile/bin/slack-vast-support-pwa";
    icon = "${config.home.homeDirectory}/.local/share/icons/hicolor/256x256/apps/slack-vast-support.png";
    terminal = false;
    extraConfig = autostartExtra;
  };

  zenAutostart = pkgs.makeDesktopItem {
    name = "zen-autostart";
    desktopName = "Zen Browser";
    exec = "${config.home.homeDirectory}/.nix-profile/bin/zen-browser";
    terminal = false;
    extraConfig = autostartExtra;
  };

  ghosttyAutostart = pkgs.makeDesktopItem {
    name = "ghostty-autostart";
    desktopName = "Ghostty";
    exec = "${pkgs.ghostty}/bin/ghostty";
    terminal = false;
    extraConfig = autostartExtra;
  };

  anyEnabled =
    cfg.beeper.enable
    || cfg.slack.enable
    || cfg.slackPwaVastSupport.enable
    || cfg.zen.enable
    || cfg.ghostty.enable;
in
{
  options.sz.autostart = {
    beeper.enable = lib.mkEnableOption "Autostart Beeper at login";

    slack.enable = lib.mkEnableOption "Autostart Slack at login";

    slackPwaVastSupport.enable = lib.mkEnableOption "Autostart Slack@VASTSupport PWA at login";

    zen.enable = lib.mkEnableOption "Autostart Zen Browser at login";

    ghostty.enable = lib.mkEnableOption "Autostart Ghostty at login";
  };

  config = lib.mkIf anyEnabled {
    xdg.autostart = {
      enable = true;
      entries =
        lib.optional cfg.beeper.enable beeperAutostart
        ++ lib.optional cfg.slack.enable "${pkgs.slack}/share/applications/slack.desktop"
        ++ lib.optional cfg.slackPwaVastSupport.enable slackPwaAutostart
        ++ lib.optional cfg.zen.enable zenAutostart
        ++ lib.optional cfg.ghostty.enable ghosttyAutostart;
    };
  };
}
