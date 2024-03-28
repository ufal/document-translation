set -euo pipefail
outdir="../output_fraus_alltexts_fixed"
mkdir -p $outdir

pipeline() {
    fullpath=$1
    file=${fullpath##*/}
    echo "Processing ${file}"
    
    if [ ! -f "$fullpath" ]; then
        echo "File $fullpath does not exist."
        return 1
    fi
    if [ -f "${outdir}/${file}.uk" ]; then
        echo "File $fullpath exists already, skipping."
        return 0
    fi

    python unescape_fraus.py --skip-xml-declaration ${fullpath} ${outdir}/${file}

    format="okf_xml@fraus.fprm"
    tikal -xm ${outdir}/${file} -fc $format -sl cs -to ${outdir}/${file}

    python escape_tool.py --unescape ${outdir}/${file}.cs ${outdir}/${file}.cs.html

    awk '{ print "<p>" $0 "</p>" }' ${outdir}/${file}.cs.html > ${outdir}/${file}.cs.p.html

    format_2="okf_html"
    tikal -xm ${outdir}/${file}.cs.p.html -fc $format_2 -sl cs -to ${outdir}/${file}.cs.second_extraction

    perl m4loc/xliff/remove_markup.pm < ${outdir}/${file}.cs.second_extraction.cs > ${outdir}/${file}.cs.second_extraction.nomarkup

    # translate and align (comment out if already computed to save time)
    time cat ${outdir}/${file}.cs.second_extraction.nomarkup | python translate.py cs uk > ${outdir}/${file}.uk.second_extraction.nomarkup
    time python align.py ${outdir}/${file}.cs.second_extraction.nomarkup ${outdir}/${file}.uk.second_extraction.nomarkup cs uk > ${outdir}/${file}.cs-uk.align.second_extraction.nomarkup

    perl m4loc/xliff/reinsert_wordalign.pm ${outdir}/${file}.cs.second_extraction.cs ${outdir}/${file}.cs-uk.align.second_extraction.nomarkup < ${outdir}/${file}.uk.second_extraction.nomarkup > ${outdir}/${file}.uk.second_extraction.uk

    tikal -lm ${outdir}/${file}.cs.p.html -fc $format_2 -sl cs -tl uk -overtrg -from ${outdir}/${file}.uk.second_extraction.uk -to ${outdir}/${file}.uk.p.html
    sed "s/^<p>\(.*\)<\/p>$/\1/" ${outdir}/${file}.uk.p.html > ${outdir}/${file}.uk.html
    tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.uk.html -to ${outdir}/${file}.uk

    # python unescape_fraus.py --skip-xml-declaration ${outdir}/${file}.reconstructed ${outdir}/${file}.reconstructed.normalized
    # tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.cs.unescaped.notags -to ${outdir}/${file}.uk
}

for file in ../data/fraus_new_batch/EdUKate_2/updated_structure/*.xml ../data/fraus_new_batch/EdUKate1/*.xml; do
    time pipeline $file
done
