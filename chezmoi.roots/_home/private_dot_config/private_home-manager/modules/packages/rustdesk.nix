{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.rustdesk;
  rustdesk = pkgs.writeShellScriptBin "rustdesk" ''
    export QT_QPA_PLATFORM=xcb
    exec ${pkgs.rustdesk}/bin/rustdesk "$@"
  '';
  rustdesk-desktop = pkgs.makeDesktopItem {
    name = "rustdesk";
    desktopName = "RustDesk";
    genericName = "Remote Desktop";
    comment = "Open source remote desktop";
    exec = "${rustdesk}/bin/rustdesk";
    tryExec = "${rustdesk}/bin/rustdesk";
    icon = "rustdesk";
    categories = [ "Network" ];
    terminal = false;
    startupNotify = true;
  };
in
{
  options.sz.packages.rustdesk.enable = lib.mkEnableOption "RustDesk remote desktop";

  config = lib.mkIf cfg.enable {
    home.packages = [
      rustdesk
      rustdesk-desktop
      (lib.lowPrio pkgs.rustdesk)
    ];
  };
}
