# Activation DAG (after installPackages):
#   syncNixDesktopEntries -> patchPinta -> patchGimp -> patchDoublecmd -> patchVicinae -> patchLibreOfficeStartcenter
# gearleverApps hooks into syncNixDesktopEntries (see services/gearlever.nix)

{ config, pkgs, lib, ... }:

let
  cfg = config.sz.platform.fedoraDesktop;
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

    # libreoffice-startcenter Desktop Actions duplicate Writer/Calc/Impress alongside
    # libreoffice-{writer,calc,impress}.desktop in GNOME/vicinae.
    home.activation.patchLibreOfficeStartcenterDesktop = lib.hm.dag.entryAfter [ "patchVicinaeDesktop" ] ''
      src="/usr/share/applications/libreoffice-startcenter.desktop"
      dst="$HOME/.local/share/applications/libreoffice-startcenter.desktop"
      if [ ! -f "$src" ]; then
        exit 0
      fi
      ${pkgs.gawk}/bin/gawk '
        BEGIN { skip = 0 }
        /^\[Desktop Action Writer\]/ { skip = 1; next }
        /^\[Desktop Action Calc\]/ { skip = 1; next }
        /^\[Desktop Action Impress\]/ { skip = 1; next }
        /^\[Desktop Action Draw\]/ { skip = 0 }
        /^\[Desktop Action Base\]/ { skip = 0 }
        /^\[Desktop Action Math\]/ { skip = 0 }
        skip { next }
        /^Actions=/ { sub(/^Actions=.*/, "Actions=Draw;Base;Math;"); print; next }
        { print }
      ' "$src" > "$dst"
      chmod a+r "$dst"
    '';
  };
}
