#!/bin/bash
set -eux

input_path="test_document.docx"
tikal="$HOME/okapi/tikal.sh"

outdir="output/"
mkdir -p $outdir

file=${input_path##*/}

extension="${file##*.}"
filename="${file%.*}"

srclang="en"
trglang="cs"
model="doc-en-cs"

# check if file exists
if [ ! -f "$input_path" ]; then
    echo "File $input_path does not exist."
    exit 1
fi

$tikal -xm $input_path -sl $srclang -to "${outdir}/$file.lines"

translate_markup "${outdir}/$file.lines".$srclang $srclang $trglang $model "${outdir}/$file.lines".$trglang --debug

$tikal -lm $input_path -sl $srclang -tl $trglang -overtrg -from "${outdir}/$file.lines".$trglang -to "${outdir}/$filename.$trglang.$extension"
