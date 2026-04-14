#!/bin/bash
set -e

# Wrapper so App Service can use a root startup command.
exec ./backend/startup.sh
