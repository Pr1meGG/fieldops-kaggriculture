#!/bin/bash
echo "Starting EXP-010..."
.venv/bin/python exp010_expansion_audit.py > exp010.out
echo "Starting EXP-011..."
.venv/bin/python exp011_worker_audit.py > exp011.out
echo "Starting EXP-012..."
.venv/bin/python exp012_livestock_audit.py > exp012.out
echo "All done!"
