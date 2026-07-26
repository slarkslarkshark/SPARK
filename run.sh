#!/bin/sh
set -e

ROOT_PATH="${SPARK_ROOT_PATH:-/spark}"

python -c "
import os
from spark.web.app import create_app
import uvicorn

root_path = os.environ.get('SPARK_ROOT_PATH', '')
app = create_app('/data', root_path=root_path)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
