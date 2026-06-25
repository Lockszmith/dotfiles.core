{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.rembg;

  rembgPkg = pkgs.python313Packages.toPythonApplication (
    pkgs.python313Packages.rembg.override {
      withCli = true;
      gradio = pkgs.python313Packages.gradio.overridePythonAttrs (old: {
        pythonRelaxDeps = (old.pythonRelaxDeps or [ ]) ++ [ "starlette" ];
      });
    }
  );

  rembg = pkgs.writeShellScriptBin "rembg" ''
    export NUMBA_CACHE_DIR="''${XDG_CACHE_HOME:-$HOME/.cache}/numba"
    mkdir -p "$NUMBA_CACHE_DIR"
    exec ${rembgPkg}/bin/rembg "$@"
  '';

  rembg-server = pkgs.writeShellScriptBin "rembg-server" ''
    if ! ${pkgs.curl}/bin/curl -sf http://127.0.0.1:7000/ >/dev/null 2>&1; then
      ${rembg}/bin/rembg s &
      for _ in $(seq 1 30); do
        ${pkgs.curl}/bin/curl -sf http://127.0.0.1:7000/ >/dev/null 2>&1 && break
        sleep 1
      done
    fi
    ${pkgs.xdg-utils}/bin/xdg-open http://localhost:7000
  '';

  rembg-desktop = pkgs.makeDesktopItem {
    name = "rembg";
    desktopName = "Rembg";
    genericName = "Background Remover";
    comment = "Remove image backgrounds (AI web UI)";
    exec = "${rembg-server}/bin/rembg-server";
    icon = "preferences-desktop-wallpaper";
    categories = [ "Graphics" "2DGraphics" ];
    terminal = false;
    startupNotify = true;
  };
in
{
  options.sz.packages.rembg.enable = lib.mkEnableOption "Rembg background removal web UI";

  config = lib.mkIf cfg.enable {
    home.packages = [
      rembg
      rembg-server
      rembg-desktop
    ];
  };
}
