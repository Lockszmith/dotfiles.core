{ config, pkgs, lib, zen-browser, ... }:

let
  cfg = config.sz.packages.zen-browser;
  zenPkg = zen-browser.packages.${pkgs.stdenv.hostPlatform.system}.default;
  zen-browser-bin = pkgs.writeShellScriptBin "zen-browser" ''
    exec ${zenPkg}/bin/zen-beta "$@"
  '';
in
{
  options.sz.packages.zen-browser.enable = lib.mkEnableOption "Zen Browser";

  config = lib.mkIf cfg.enable {
    home.packages = [
      zen-browser-bin
      (lib.lowPrio zenPkg)
    ];
  };
}
