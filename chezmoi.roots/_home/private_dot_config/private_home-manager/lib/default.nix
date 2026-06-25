{
  home-manager,
  pkgs,
  zen-browser,
  nix-software-center,
  vicinae,
}:

let
  mkHost =
    {
      name,
      extraModules ? [ ],
    }:
    home-manager.lib.homeManagerConfiguration {
      inherit pkgs;
      extraSpecialArgs = {
        inherit zen-browser nix-software-center;
      };
      modules = [
        ./../modules/default.nix
        ./../hosts/default.nix
        (./../hosts + "/${name}.nix")
        vicinae.homeManagerModules.default
      ]
      ++ extraModules;
    };
in
{
  inherit mkHost;
}
