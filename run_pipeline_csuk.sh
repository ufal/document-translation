outdir="../output"

python unescape_fraus.py --skip-xml-declaration ../data/1892.xml ${outdir}/1892.xml
# python fix_fraus_xml_encoding.py ../data/1892.xml ${outdir}/1892.xml

format="okf_xml@fraus.fprm"
tikal -xm ${outdir}/1892.xml -fc $format -sl cs -to ${outdir}/1892.xml

python escape_tool.py --unescape ${outdir}/1892.xml.cs ${outdir}/1892.xml.cs.unescaped

# remove tags
sed 's/<[^>]*>//g' ${outdir}/1892.xml.cs.unescaped > ${outdir}/1892.xml.cs.unescaped.notags

echo "Translation"
cat "${outdir}/1892.xml.cs.unescaped.notags" | python translate.py  > "${outdir}/1892.xml.uk.unescaped.notags"

tikal -lm ${outdir}/1892.xml -fc $format -sl cs -tl uk -overtrg -from ${outdir}/1892.xml.cs.unescaped.notags -to ${outdir}/1892.xml.uk
