#!/bin/sh
# ROM with ARM patches only (no override library needed, runs on hardware): code.bin -> arm_patches.py (A1) -> build_arm_native.py
# (French text engine compiled for the ARM11, cavity + hooks + bss extension) -> ExeFS -> CXI.
# Input: work/rom/{exefs.bin,header.bin,exheader.bin,logo.bin,plain.bin,romfs_fr.bin}. Output: work/rom/game_arm.cxi (run `build_all.sh` first)
set -e
cd "$(dirname "$0")/../work/rom"
rm -rf exefs_arm && ../../externals/3dstool -xtfu exefs exefs.bin --exefs-dir exefs_arm --header exefs_header.bin >/dev/null
python3 -I ../../tools/arm_patches.py exefs_arm/code.bin exefs_arm/code.bin
python3 ../../tools/build_arm_native.py exefs_arm/code.bin exefs_arm/code.bin exheader.bin exheader_arm.bin
../../externals/3dstool -ctf exefs exefs_arm.bin --exefs-dir exefs_arm --header exefs_header.bin --compress >/dev/null
../../externals/3dstool -ctf cxi game_arm.cxi --header header.bin --exh exheader_arm.bin --logo logo.bin --plain plain.bin --exefs exefs_arm.bin --romfs romfs_fr.bin --not-encrypt >/dev/null
../../externals/ctrtool game_arm.cxi 2>&1 | grep -E "Crypto Key|ExeFS size" ; echo "OK -> work/rom/game_arm.cxi"
