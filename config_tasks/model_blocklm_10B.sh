MODEL_TYPE="blocklm-10B"
MODEL_ARGS="--block-lm \
            --cloze-eval \
            --task-mask \
            --num-layers 48 \
            --hidden-size 4096 \
            --num-attention-heads 64 \
            --max-position-embeddings 1024 \
            --tokenizer-type GPT2BPETokenizer \
            --load-pretrained /dataset/c07bd62b/checkpoints/blocklm-10b04-19-11-09_MP4"