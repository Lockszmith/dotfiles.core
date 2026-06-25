{ ... }:

{
  programs.zsh = {
    enable = true;
    initContent = ''
      # This is added by home-manager under programs.zsh.initContent
      [ -s "$HOME/.config/sz.env/000_load.sh" ] && . <( "$HOME/.config/sz.env/000_load.sh" - )
    '';
  };
}
