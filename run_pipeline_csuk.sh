outdir="../output"
mkdir -p $outdir
file="1892.xml"

python unescape_fraus.py --skip-xml-declaration ../data/${file} ${outdir}/${file}
# python fix_fraus_xml_encoding.py ../data/${file} ${outdir}/${file}

format="okf_xml@fraus.fprm"
tikal -xm ${outdir}/${file} -fc $format -sl cs -to ${outdir}/${file}

python escape_tool.py --unescape ${outdir}/${file}.cs ${outdir}/${file}.cs.html

awk '{ print "<p>" $0 "</p>" }' ${outdir}/${file}.cs.html > ${outdir}/${file}.cs.p.html

format_2="okf_html"
tikal -xm ${outdir}/${file}.cs.p.html -fc $format_2 -sl cs -to ${outdir}/${file}.cs.second_extraction

perl m4loc/xliff/remove_markup.pm < ${outdir}/${file}.cs.second_extraction.cs > ${outdir}/${file}.cs.second_extraction.nomarkup

# translate and align (comment out if already computed to save time)
cat ${outdir}/${file}.cs.second_extraction.nomarkup | python translate.py > ${outdir}/${file}.uk.second_extraction.nomarkup
python align.py ${outdir}/${file}.cs.second_extraction.nomarkup ${outdir}/${file}.uk.second_extraction.nomarkup > ${outdir}/${file}.cs-uk.align.second_extraction.nomarkup

perl m4loc/xliff/reinsert_wordalign.pm ${outdir}/${file}.cs.second_extraction.cs ${outdir}/${file}.cs-uk.align.second_extraction.nomarkup < ${outdir}/${file}.uk.second_extraction.nomarkup > ${outdir}/${file}.uk.second_extraction.uk

tikal -lm ${outdir}/${file}.cs.p.html -fc $format_2 -sl cs -tl uk -overtrg -from ${outdir}/${file}.uk.second_extraction.uk -to ${outdir}/${file}.uk.p.html
sed "s/^<p>\(.*\)<\/p>$/\1/" ${outdir}/${file}.uk.p.html > ${outdir}/${file}.uk.html
tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.uk.html -to ${outdir}/${file}.uk

# python unescape_fraus.py --skip-xml-declaration ${outdir}/${file}.reconstructed ${outdir}/${file}.reconstructed.normalized
# tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.cs.unescaped.notags -to ${outdir}/${file}.uk




# OLD

# remove tags
# sed 's/<[^>]*>//g' ${outdir}/${file}.cs.unescaped > ${outdir}/${file}.cs.unescaped.notags

# echo "Translation"
# cat "${outdir}/${file}.cs.unescaped.notags" | python translate.py > "${outdir}/${file}.uk.unescaped.notags"

# python align.py ${outdir}/${file}.cs.unescaped.notags ${outdir}/${file}.uk.unescaped.notags > ${outdir}/${file}.alignments
