#!/bin/sh
# Run on the AI host only; no existing container or service is managed here.
set -eu
base=/home/awendelk/adapter-diagnostics-20261006
for mode in native-query native-passage onnx v5; do
    source_dir=$base/v3-source
    if [ "$mode" = v5 ]; then
        source_dir=/home/awendelk/controlled-retrieval-20261006/v5-source
    fi
    sudo -n docker run --rm --name "uranus-adapter-diagnostic-$mode-20261006" \
        --network none --read-only --cpus 8 --memory 6g --memory-swap 8g \
        --pids-limit 256 --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,size=512m \
        -e ISOLATED_ADAPTER_DIAGNOSTICS=1 -e HF_HUB_OFFLINE=1 \
        -e TRANSFORMERS_OFFLINE=1 -e HF_HUB_DISABLE_PROGRESS_BARS=1 \
        -e PYTHONDONTWRITEBYTECODE=1 -e TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor \
        -e PYTHONPATH=/encoder/src \
        -v /home/awendelk/uranus-research-encoder/.venv:/bench-venv:ro \
        -v /home/awendelk/.local/share/uv/python:/home/awendelk/.local/share/uv/python:ro \
        -v "$source_dir":/encoder:ro -v "$base/input":/input:ro \
        -v "$base/contracts":/contracts:ro -v "$base/output":/output:rw \
        -v /srv/uranus-research-encoder/merged-v1:/merged:ro \
        -v /srv/uranus-research-encoder-onnx-test:/v3cache:ro \
        -v /srv/uranus-research-encoder/v5-stage/hf/hub:/v5cache:ro \
        --entrypoint /bench-venv/bin/python \
        sha256:6834c50c52bd7e60f6a6d25772102198dd9638b3dc33859e6bf05df9a67b2c1b \
        /input/isolated_adapter_diagnostics.py "$mode" --plan /input/plan.json \
        --contracts /contracts --output "/output/$mode.json"
done
