@echo off
cd /d "%~dp0"
git init
git add .
git commit -m "Initial commit: Kernel One implementation"
echo Git repository initialized and committed successfully!
pause