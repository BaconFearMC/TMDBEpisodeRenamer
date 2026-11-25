@echo off
title TMDB Episode Renamer
cd /d "%~dp0"
py -3 "TMDB_Episode_Renamer.py"
if errorlevel 1 (
    echo.
    echo Could not start the app. Make sure Python 3 is installed with Tkinter.
    pause
)
