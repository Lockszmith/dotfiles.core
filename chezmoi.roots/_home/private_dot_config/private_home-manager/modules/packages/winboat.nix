{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.winboat;
in
{
  options.sz.packages.winboat.enable = lib.mkEnableOption "Winboat (ControlR) with GStreamer deps";

  config = lib.mkIf cfg.enable {
    home.packages = with pkgs; [
      winboat
      gst_all_1.gstreamer
      gst_all_1.gst-plugins-base
      gst_all_1.gst-plugins-good
    ];
  };
}
