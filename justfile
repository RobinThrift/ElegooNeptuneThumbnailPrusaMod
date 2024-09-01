venv_bin := "./.venv/bin"

venv:
    [ -d .venv ] || (python3 -m venv .venv && just install)

install:
    {{ venv_bin }}/pip install -r requirements.txt

package *flags="--standalone --onefile --output-dir=build --remove-output --output-filename=gen_thumbnail": venv
    {{ venv_bin }}/nuitka {{ flags }} thumbnail.py

pip +cmd: venv
    {{ venv_bin }}/pip {{ cmd }}
