@echo off
REM Memex launcher for Windows
REM This is a simple wrapper that delegates to the main Memex CLI

REM Pass all arguments to memex_cli.py
python "%~dp0memex_cli.py" %*