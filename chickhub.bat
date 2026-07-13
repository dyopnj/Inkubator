@echo off
cd /d "%~dp0server"
echo ChickHub Server: http://localhost:3000
echo Login: admin / admin
node index.js
