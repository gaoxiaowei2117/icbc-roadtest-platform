#!/bin/bash
# Codex 沙箱下让 git 在本项目可用的环境变量。
# 原因：项目内的 .git 路径被沙箱以只读方式挂载，git 命令直接跑会报
#       "could not lock config file .../.git/config: Read-only file system"。
# 用法：在本项目目录下执行  source .git-env.sh  之后当前 shell 就能正常用 git。
# 重新打开终端需要再 source 一次。
# 退出沙箱会话后此文件可以删掉，不再需要。
export GIT_DIR=/tmp/icbc-git
export GIT_WORK_TREE=/home/xgao/workspace/icbc-roadtest-platform
