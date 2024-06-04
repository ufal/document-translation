set -euxo pipefail

datadir="../data"
outdir="../output"
mkdir -p $outdir
file="balservis.html"
srclang="cs"
trglang="en"

# check if file exists
if [ ! -f "$datadir/$file" ]; then
    echo "File $datadir/$file does not exist."
    exit 1
fi

cp $datadir/$file $outdir

tikal -xm ${outdir}/${file} -sl $srclang -to ${outdir}/${file}

time python translate_markup.py ${outdir}/${file}.$srclang $srclang $trglang ${outdir}/${file}.$trglang

tikal -lm ${outdir}/${file} -sl $srclang -tl $trglang -overtrg -from ${outdir}/${file}.$trglang -to ${outdir}/${file}.$trglang
