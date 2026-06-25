{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.ghostty;
in
{
  options.sz.packages.ghostty.enable = lib.mkEnableOption "Ghostty terminal";

  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.ghostty ];
  };
}
