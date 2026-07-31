# Minimal example

```bash
pip install -e ../..
solaris-board init --root . --name Minimal --project Eng --force
export BOARD_ROOT=$PWD
solaris-board task create --title "Hello" --project Eng --build
solaris-board export
```
