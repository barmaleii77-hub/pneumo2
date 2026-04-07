@echo off
setlocal
echo Starting Dask scheduler on port 8786...
dask scheduler --host 0.0.0.0 --port 8786
