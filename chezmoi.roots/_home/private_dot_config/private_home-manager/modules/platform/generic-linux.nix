{ config, lib, ... }:

let
  cfg = config.sz.platform.genericLinux;
in
{
  options.sz.platform.genericLinux.enable = lib.mkEnableOption "genericLinux target for non-NixOS systems";

  config = lib.mkIf cfg.enable {
    targets.genericLinux.enable = true;
  };
}
