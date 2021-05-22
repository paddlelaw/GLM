EXPERIMENT_NAME=${MODEL_TYPE}-squad
TASK_NAME=squad
DATA_PATH="/dataset/c07bd62b/SQuAD"
MAX_SEQ_LEN=448

LR_SINGLE=1e-5
EPOCH_SINGLE=4

TRAIN_ARGS="--lr-decay-style linear \
            --warmup 0.1 \
            --weight-decay 1.0e-1"

COMMON_ARGS="--save-interval 10000 \
             --log-interval 50 \
             --eval-interval 1000 \
             --eval-iters 100"

PATTERN_IDS=(0)
PROMPT_IDS=(1)

BATCH_SIZE=16