#!/bin/sh
set -e

ROOT_PATH="${SPARK_ROOT_PATH:-/spark}"

echo "Starting SPARK runtime with ROOT_PATH=$ROOT_PATH"

exec python -c "
from spark.web.app import create_app
import uvicorn
app = create_app('/data', root_path='$ROOT_PATH')
uvicorn.run(app, host='0.0.0.0', port=8000)
"
