# Minimal example

```bash
pip install -e ../..
# board_dir defaults to this folder's basename; use --board-dir Board for legacy
solaris init --root . --name Minimal --project Eng --force
export BOARD_ROOT=$PWD
solaris task create --title "Hello" --project Eng --build
solaris export
ls Welcome.md Notes To\ Do.md Wiki "$PWD"/*/config.yml
```
