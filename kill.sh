#!/bin/bash
sudo kill -9 $(ps aux | grep 'ambicam/app.py' | grep -v grep | awk {'print $2'} | xargs)