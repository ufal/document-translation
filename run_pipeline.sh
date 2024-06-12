set -euxo pipefail
outdir="../output"
mkdir -p $outdir
# input_path="../data/test.docx"
# input_path="../data/kuba.pptx"
# input_path="../data/wiki_materidouska.odt"
# input_path="../data_kofranek/old/kofranek0/dejiny00.odt"
input_path="../data_kofranek/kofranek/Dějiny klasické anatomie_část_0_a_1.docx"
file=${input_path##*/}

extension="${file##*.}"
filename="${file%.*}"

srclang="cs"
trglang="en"
model="cs-en"

# check if file exists
if [ ! -f "$input_path" ]; then
    echo "File $input_path does not exist."
    exit 1
fi

cp "$input_path" $outdir

tikal -xm "${outdir}/$file" -sl $srclang -to "${outdir}/$file.lines"

time python -m cProfile -o perf.stats translate_markup.py "${outdir}/$file.lines".$srclang $srclang $trglang $model "${outdir}/$file.lines".$trglang

tikal -lm "${outdir}/$file" -sl $srclang -tl $trglang -overtrg -from "${outdir}/$file.lines".$trglang -to "${outdir}/$filename.$trglang.$extension"
