set -euxo pipefail
outdir="../output"
mkdir -p $outdir
# input_path="../data/edge_cases.html"
input_path="../data_kofranek/old/kofranek0/dejiny00.odt"
file=${input_path##*/}

srclang="cs"
trglang="en"

# check if file exists
if [ ! -f "$input_path" ]; then
    echo "File $input_path does not exist."
    exit 1
fi

cp "$input_path" $outdir

tikal -xm "${outdir}/${file}" -sl $srclang -to "${outdir}/${file}.lines"

time python translate_markup.py "${outdir}/${file}.lines".$srclang $srclang $trglang "${outdir}/${file}.lines".$trglang

tikal -lm "${outdir}/${file}" -sl $srclang -tl $trglang -overtrg -from "${outdir}/${file}.lines".$trglang -to "${outdir}/${file}".$trglang
