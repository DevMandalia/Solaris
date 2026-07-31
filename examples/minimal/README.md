# Minimal example

```bash
pip install -e ../..
solaris init --root . --name Minimal --project Eng --force
export BOARD_ROOT=$PWD
solaris task create --title "Hello" --project Eng --build
solaris export
```
