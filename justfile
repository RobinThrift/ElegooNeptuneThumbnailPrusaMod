venv_bin := "./.venv/bin"

venv:
    [ -d .venv ] || (python3 -m venv .venv && just install)

install:
    {{ venv_bin }}/pip install -r requirements.txt

pip +cmd: venv
    {{ venv_bin }}/pip {{cmd}}
