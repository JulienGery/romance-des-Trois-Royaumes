#!/bin/sh
# ROM with ARM patches only (no override library needed, runs on hardware): code.bin -> arm_patches.py (A1) -> build_arm_native.py
# (French text engine compiled for the ARM11, cavity + hooks + bss extension) -> ExeFS -> CXI.
# Input: rom_work/{exefs.bin,header.bin,exheader.bin,logo.bin,plain.bin,romfs_fr.bin}. Output: rom_work/game_arm.cxi (run `build_all.sh` first)
set -e
cd "$(dirname "$0")/../rom_work"
rm -rf exefs_arm && ../3dstool -xtfu exefs exefs.bin --exefs-dir exefs_arm --header exefs_header.bin >/dev/null
python3 -I ../fr_patch/arm_patches.py exefs_arm/code.bin exefs_arm/code.bin
python3 ../fr_patch/build_arm_native.py exefs_arm/code.bin exefs_arm/code.bin exheader.bin exheader_arm.bin
../3dstool -ctf exefs exefs_arm.bin --exefs-dir exefs_arm --header exefs_header.bin --compress >/dev/null
../3dstool -ctf cxi game_arm.cxi --header header.bin --exh exheader_arm.bin --logo logo.bin --plain plain.bin --exefs exefs_arm.bin --romfs romfs_fr.bin --not-encrypt >/dev/null
../ctrtool game_arm.cxi 2>&1 | grep -E "Crypto Key|ExeFS size" ; echo "OK -> rom_work/game_arm.cxi"
