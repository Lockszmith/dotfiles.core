{ config, pkgs, lib, ... }:

let
  cfg = config.sz.activations.setDefaultShell;
in
{
  options.sz.activations.setDefaultShell.enable = lib.mkEnableOption "set zsh as user login shell and /bin/sh for root";

  config = lib.mkIf cfg.enable {
    home.activation.setDefaultShell = lib.hm.dag.entryAfter [ "installPackages" ] ''
      set +e
      zsh_bin="${pkgs.zsh}/bin/zsh"
      root_shell="/bin/sh"
      getent=/bin/getent
      chsh=/usr/bin/chsh

      user_shell=$("$getent" passwd "${config.home.username}" | cut -d: -f7)
      root_current=$("$getent" passwd root | cut -d: -f7)
      zsh_in_shells=false
      grep -Fxq "$zsh_bin" /etc/shells 2>/dev/null && zsh_in_shells=true

      user_ok=false
      [ "$user_shell" = "$zsh_bin" ] && user_ok=true
      root_ok=false
      [ "$root_current" = "/bin/sh" ] || [ "$root_current" = "/bin/dash" ] && root_ok=true

      needs_sudo=false
      needs_user_chsh=false
      if [ "$user_ok" = false ]; then
        if [ "$zsh_in_shells" = false ]; then
          needs_sudo=true
        else
          needs_user_chsh=true
        fi
      fi
      [ "$root_ok" = false ] && needs_sudo=true

      if [ "$needs_user_chsh" = true ] && [ -x "$zsh_bin" ]; then
        $DRY_RUN_CMD "$chsh" -s "$zsh_bin" "${config.home.username}" </dev/null 2>/dev/null || true
      fi

      if [ "$needs_sudo" = true ]; then
        if [ -n "''${SUDO:-}" ]; then
          if [ "$zsh_in_shells" = false ] && [ -f "$zsh_bin" ]; then
            echo "$zsh_bin" | $DRY_RUN_CMD "$SUDO" tee -a /etc/shells >/dev/null
            grep -Fxq "$zsh_bin" /etc/shells 2>/dev/null && zsh_in_shells=true
          fi
          if [ "$root_ok" = false ]; then
            $DRY_RUN_CMD "$SUDO" chsh -s "$root_shell" root </dev/null 2>/dev/null || true
          fi
          if [ "$user_ok" = false ] && [ "$zsh_in_shells" = true ] && [ -x "$zsh_bin" ]; then
            user_shell=$("$getent" passwd "${config.home.username}" | cut -d: -f7)
            if [ "$user_shell" != "$zsh_bin" ]; then
              $DRY_RUN_CMD "$chsh" -s "$zsh_bin" "${config.home.username}" </dev/null 2>/dev/null || true
            fi
          fi
        else
          echo "login shells need updating (${config.home.username} -> zsh, root -> /bin/sh)."
          echo "Re-run with: SUDO=sudo home-manager switch --flake .#sz"
        fi
      fi
      set -e
    '';
  };
}
