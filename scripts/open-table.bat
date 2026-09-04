@echo off
rem 一键开打：确保常驻服务在跑，然后开夜场窗口
schtasks /run /tn PokerGym >nul 2>&1
timeout /t 1 /nobreak >nul
start "" msedge --app=http://127.0.0.1:8765/ --window-size=1480,920 2>nul || start "" http://127.0.0.1:8765/
