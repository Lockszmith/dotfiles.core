# Activation DAG (after installPackages):
#   syncNixDesktopEntries -> patchPinta -> patchGimp -> patchDoublecmd -> patchVicinae -> patchDuplicateDesktopActions
# gearleverApps hooks into syncNixDesktopEntries (see services/gearlever.nix)

{ config, pkgs, lib, ... }:

let
  cfg = config.sz.platform.fedoraDesktop;

  dedupHelper = pkgs.writeShellScript "dedup-desktop-helper" ''
    exec ${pkgs.python3}/bin/python3 ${./dedup-desktop-entries.py} "$@"
  '';
in
{
  config = lib.mkIf cfg.enable {
    home.activation.patchPintaDesktop = lib.hm.dag.entryAfter [ "syncNixDesktopEntries" ] ''
      pinta_desktop="$HOME/.local/share/applications/com.github.PintaProject.Pinta.desktop"
      pinta_bin="$HOME/.nix-profile/bin/pinta"
      if [ -f "$pinta_desktop" ] && [ -x "$pinta_bin" ]; then
        ${pkgs.gnused}/bin/sed -i "s|^Exec=.*|Exec=$pinta_bin %F|" "$pinta_desktop"
        ${pkgs.gnused}/bin/sed -i "s|^TryExec=.*|TryExec=$pinta_bin|" "$pinta_desktop"
      fi
    '';

    home.activation.patchGimpDesktop = lib.hm.dag.entryAfter [ "patchPintaDesktop" ] ''
      gimp_desktop="$HOME/.local/share/applications/gimp.desktop"
      gimp_bin="$HOME/.nix-profile/bin/gimp"
      if [ -f "$gimp_desktop" ] && [ -x "$gimp_bin" ]; then
        ${pkgs.gnused}/bin/sed -i "s|^Exec=.*|Exec=$gimp_bin %U|" "$gimp_desktop"
        ${pkgs.gnused}/bin/sed -i "s|^TryExec=.*|TryExec=$gimp_bin|" "$gimp_desktop"
      fi
    '';

    home.activation.patchDoublecmdDesktop = lib.hm.dag.entryAfter [ "patchGimpDesktop" ] ''
      dc_desktop="$HOME/.local/share/applications/doublecmd.desktop"
      dc_bin="$HOME/.nix-profile/bin/doublecmd"
      if [ -f "$dc_desktop" ] && [ -x "$dc_bin" ]; then
        ${pkgs.gnused}/bin/sed -i "s|^Exec=.*|Exec=$dc_bin %F|" "$dc_desktop"
        ${pkgs.gnused}/bin/sed -i "s|^TryExec=.*|TryExec=$dc_bin|" "$dc_desktop"
      fi
    '';

    home.activation.patchVicinaeDesktop = lib.hm.dag.entryAfter [ "patchDoublecmdDesktop" ] ''
      vicinae_desktop="$HOME/.local/share/applications/vicinae.desktop"
      vicinae_bin="$HOME/.nix-profile/bin/vicinae"
      if [ -f "$vicinae_desktop" ] && [ -x "$vicinae_bin" ]; then
        ${pkgs.gnused}/bin/sed -i "0,/^\[Desktop Action/ s|^Exec=.*|Exec=$vicinae_bin open|" "$vicinae_desktop"
        ${pkgs.gnused}/bin/sed -i "/^\[Desktop Action close\]/,/^\[/ s|^Exec=.*|Exec=$vicinae_bin close|" "$vicinae_desktop"
        ${pkgs.gnused}/bin/sed -i "/^\[Desktop Action toggle\]/,/^\[/ s|^Exec=.*|Exec=$vicinae_bin toggle|" "$vicinae_desktop"
        if ! grep -q "^TryExec=" "$vicinae_desktop"; then
          ${pkgs.gnused}/bin/sed -i "/^Exec=/a TryExec=$vicinae_bin" "$vicinae_desktop"
        else
          ${pkgs.gnused}/bin/sed -i "s|^TryExec=.*|TryExec=$vicinae_bin|" "$vicinae_desktop"
        fi
      fi
    '';

    # Strip Desktop Actions whose Exec matches a standalone .desktop elsewhere (e.g. startcenter Writer/Calc/Impress).
    home.activation.patchDuplicateDesktopActions = lib.hm.dag.entryAfter [ "patchVicinaeDesktop" ] ''
      $DRY_RUN_CMD ${dedupHelper} patch-actions
    '';
  };
}
