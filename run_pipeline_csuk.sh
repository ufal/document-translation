outdir="../output"
mkdir -p $outdir
file="1892.xml"

python unescape_fraus.py --skip-xml-declaration ../data/${file} ${outdir}/${file}
# python fix_fraus_xml_encoding.py ../data/${file} ${outdir}/${file}

format="okf_xml@fraus.fprm"
tikal -xm ${outdir}/${file} -fc $format -sl cs -to ${outdir}/${file}

python escape_tool.py --unescape ${outdir}/${file}.cs ${outdir}/${file}.cs.html

format_2="okf_html"
tikal -xm ${outdir}/${file}.cs.html -fc $format_2 -sl cs -to ${outdir}/${file}.cs.second_extraction

# remove tags
# sed 's/<[^>]*>//g' ${outdir}/${file}.cs.unescaped > ${outdir}/${file}.cs.unescaped.notags

# echo "Translation"
# cat "${outdir}/${file}.cs.unescaped.notags" | python translate.py > "${outdir}/${file}.uk.unescaped.notags"

# python align.py ${outdir}/${file}.cs.unescaped.notags ${outdir}/${file}.uk.unescaped.notags > ${outdir}/${file}.alignments

# tikal -lm ${outdir}/${file} -fc $format -sl cs -tl uk -overtrg -from ${outdir}/${file}.cs.unescaped.notags -to ${outdir}/${file}.uk
