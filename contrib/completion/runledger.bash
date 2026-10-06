# Bash completion for the runledger CLI.
#
# Install for the current user:
#   mkdir -p ~/.local/share/bash-completion/completions
#   cp contrib/completion/runledger.bash ~/.local/share/bash-completion/completions/runledger
# Or source it directly from ~/.bashrc:
#   source /path/to/runledger/contrib/completion/runledger.bash

_runledger() {
    local cur prev words cword subcommand bundle_action i w
    # shellcheck disable=SC2034
    _init_completion -n : 2>/dev/null || {
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
    }

    local -r SUBCOMMANDS="init exec recover compare bundle verify report"

    # Find the active subcommand (and bundle action) from earlier words.
    subcommand=""
    bundle_action=""
    for ((i = 1; i < cword; i++)); do
        w="${words[i]}"
        case "$w" in
            init | exec | recover | compare | bundle | verify | report)
                subcommand="$w"
                ;;
            create | verify)
                if [[ "$subcommand" == "bundle" ]]; then
                    bundle_action="$w"
                fi
                ;;
        esac
    done

    # Complete the value of an option that takes one.
    case "$prev" in
        --format)
            case "$subcommand" in
                compare) COMPREPLY=($(compgen -W "markdown json" -- "$cur")) ;;
                report) COMPREPLY=($(compgen -W "markdown json html sarif" -- "$cur")) ;;
            esac
            return 0
            ;;
        --repo | --run-dir | --contract | --output)
            _filedir 2>/dev/null || COMPREPLY=($(compgen -f -- "$cur"))
            return 0
            ;;
        --run-id | --timeout)
            # Free-form values: nothing sensible to complete.
            return 0
            ;;
    esac

    # Bundle's nested actions.
    if [[ "$subcommand" == "bundle" && -z "$bundle_action" ]]; then
        if [[ "$cur" == -* ]]; then
            COMPREPLY=($(compgen -W "--help" -- "$cur"))
        else
            COMPREPLY=($(compgen -W "create verify" -- "$cur"))
        fi
        return 0
    fi

    # No subcommand yet: complete subcommand names.
    if [[ -z "$subcommand" ]]; then
        COMPREPLY=($(compgen -W "$SUBCOMMANDS" -- "$cur"))
        return 0
    fi

    # Options for the active subcommand (or bundle action).
    local opts="--help"
    case "$subcommand" in
        init) opts="$opts --repo --run-dir --run-id" ;;
        exec) opts="$opts --repo --run-dir --timeout --pty --isolated" ;;
        recover) opts="$opts --run-dir" ;;
        compare) opts="$opts --format --output" ;;
        verify) opts="$opts --run-dir --contract" ;;
        report) opts="$opts --run-dir --format --output" ;;
        bundle)
            case "$bundle_action" in
                create) opts="$opts --run-dir --output" ;;
                verify) opts="$opts --output" ;;
            esac
            ;;
    esac

    if [[ "$cur" == -* ]]; then
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        return 0
    fi

    # `exec` takes a command after the options: fall back to normal
    # command-name/file completion. Everything else takes no positionals
    # worth completing here (run-dir paths were handled via --run-dir).
    if [[ "$subcommand" == "exec" ]]; then
        _command 2>/dev/null || {
            COMPREPLY=($(compgen -c -- "$cur"))
            return 0
        }
    fi
    return 0
}

complete -F _runledger runledger
