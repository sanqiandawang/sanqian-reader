#!/bin/bash
cd /Users/zzp/Desktop/claudecode/sanqian-reader
source venv/bin/activate
python pipeline.py >> data/daily.log 2>&1
