#!/bin/bash
export TESSDATA_PREFIX=/home/claude/tessdata
cd /home/claude/ocr
for name in loi-2016-16 decret-2020-198 loi-2008-07; do
  pdf=/mnt/user-data/uploads/$name.pdf
  mkdir -p $name
  n=$(pdfinfo "$pdf" | awk '/^Pages:/{print $2}')
  for p in $(seq 1 $n); do
    pp=$(printf "%03d" $p)
    [ -s $name/p$pp.txt ] && continue
    pdftoppm -r 220 -gray -png -f $p -l $p "$pdf" /tmp/pg_$name
    img=$(ls /tmp/pg_$name-*.png | head -1)
    tesseract "$img" $name/p$pp -l fra --psm 6 >/dev/null 2>&1
    rm -f /tmp/pg_$name-*.png
    echo "$name $p/$n" > progress.txt
  done
done
echo DONE > progress.txt
