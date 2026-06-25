{ config, lib, ... }:

let
  cfg = config.sz.desktop.plasmaKeyboard;
in
{
  options.sz.desktop.plasmaKeyboard.enable = lib.mkEnableOption "KDE Plasma keyboard layout via kxkbrc";

  config = lib.mkIf cfg.enable {
    home.keyboard = null;

    xdg.configFile."kxkbrc".text = ''
      [Layout]
      DisplayNames=,
      LayoutList=us,il
      Options=shift:both_capslock,caps:escape
      ResetOldOptions=true
      SwitchMode=Window
      Use=true
      VariantList=,
    '';
  };
}
