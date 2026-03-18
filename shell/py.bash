py() {
  local app_bin="${HOME}/.py/bin/py"
  local script

  if [[ ! -x "$app_bin" ]]; then
    printf '%s\n' "py is not installed at ${app_bin}" >&2
    return 127
  fi

  case "${1:-}" in
    ""|-h|-v|-u|ls|which)
      "$app_bin" "$@"
      return $?
      ;;
  esac

  script="$("$app_bin" "$@")" || return $?
  eval "$script"
}
