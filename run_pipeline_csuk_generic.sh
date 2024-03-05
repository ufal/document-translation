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

perl m4loc/xliff/remove_markup.pm < ${outdir}/${file}.$srclang > ${outdir}/${file}.$srclang.nomarkup

# translate and align (comment out if already computed to save time)
echo "Translate"
time cat ${outdir}/${file}.$srclang.nomarkup | python translate.py $srclang $trglang > ${outdir}/${file}.$trglang.nomarkup
echo "Align"
time python align.py ${outdir}/${file}.$srclang.nomarkup ${outdir}/${file}.$trglang.nomarkup $srclang $trglang > ${outdir}/${file}.$srclang-$trglang.align.nomarkup

perl m4loc/xliff/reinsert_wordalign.pm ${outdir}/${file}.$srclang ${outdir}/${file}.$srclang-$trglang.align.nomarkup < ${outdir}/${file}.$trglang.nomarkup > ${outdir}/${file}.$trglang.withmarkup
tikal -lm ${outdir}/${file} -sl $srclang -tl $trglang -overtrg -from ${outdir}/${file}.$trglang.withmarkup -to ${outdir}/${file}.$trglang

# python unescape_fraus.py --skip-xml-declaration ${outdir}/${file}.reconstructed ${outdir}/${file}.reconstructed.normalized
# tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.cs.unescaped.notags -to ${outdir}/${file}.uk




# OLD

# remove tags
# sed 's/<[^>]*>//g' ${outdir}/${file}.cs.unescaped > ${outdir}/${file}.cs.unescaped.notags

# echo "Translation"
# cat "${outdir}/${file}.cs.unescaped.notags" | python translate.py > "${outdir}/${file}.uk.unescaped.notags"

# python align.py ${outdir}/${file}.cs.unescaped.notags ${outdir}/${file}.uk.unescaped.notags > ${outdir}/${file}.alignments
